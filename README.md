# Airport Taxi Time Big Data

Dự án phân tích TaxiOut của chuyến bay Hoa Kỳ năm 2008. Notebook Kaggle xử lý dữ liệu bằng Apache Spark và huấn luyện H2O AutoML. Dashboard Streamlit ở máy local nạp **mô hình H2O binary thật** đã xuất từ Kaggle.

## Trạng thái đã kiểm chứng

| Thành phần | Trạng thái |
| --- | --- |
| Spark trên Kaggle | Đã xử lý 6.853.707 chuyến năm 2008 |
| H2O AutoML | GLM tốt nhất; MAE 5,8445 phút; RMSE 10,0755; R² 0,2034 |
| Dự đoán local trong Ubuntu WSL | Đã nạp mô hình `GLM_1_AutoML_2_20261002_33511` và dự đoán mẫu 22,40 phút |
| HDFS local một nút | Đã chạy NameNode + 1 DataNode; Spark đọc CSV trên HDFS, lọc 5 chuyến hợp lệ và ghi hai bảng Parquet về HDFS |
| Dữ liệu chuyến bay thời gian thực | Đã tích hợp snapshot Aviationstack theo sân bay; CSV vẫn là nguồn dự phòng |

Nguồn: [Kaggle notebook](https://www.kaggle.com/code/evelynphuong/bigdata?scriptVersionId=354555139). Tập gốc là `bulter22/airline-data`; không tải toàn bộ 11,2 GB về máy local.

## Mở dashboard trong Ubuntu WSL

```bash
cd "/mnt/c/Users/Phuong Uyen/OneDrive/Documents/ChatGPT/BigData"
~/bigdata-venv/bin/python -m streamlit run app.py
```

Mở `http://localhost:8501` trên Windows. Trong tab dự đoán, dòng nguồn phải ghi `H2O AutoML — GLM_1_AutoML_2_20261002_33511`; nếu ghi công thức dự phòng thì kết quả **không** đến từ mô hình H2O.

`test_h2o_local.py` là phép thử ngắn cho mô hình thật:

```bash
~/bigdata-venv/bin/python test_h2o_local.py
```

## Biểu đồ theo giờ

Nếu `data/hourly_congestion_top20.csv` được tải từ Kaggle, dashboard dùng số liệu tắc nghẽn đầy đủ năm 2008. Bản Kaggle đã lưu hiện không cung cấp tệp này trong Output. Khi thiếu tệp, dashboard dựng **TaxiOut trung bình và số chuyến theo giờ của tháng 1–9/2008** từ `taxiout_deployment_v3/origin_hour_hist.csv`. Đây là dữ liệu lịch sử thật, nhưng **không** phải số cửa sổ quá tải cả năm. Không có `error_by_hour_v3.csv` thì biểu đồ MAE theo giờ để trống; không nội suy từ các bảng sai số khác.

## HDFS một nút trong WSL

`setup_hdfs_wsl.sh` tải Apache Hadoop 3.5.0 từ kho Apache, kiểm tra SHA-512, cấu hình NameNode và DataNode trên Ubuntu WSL. Cụm này là **pseudo-distributed một máy** để kiểm chứng HDFS, không phải cụm sản xuất nhiều máy.

```bash
bash setup_hdfs_wsl.sh
~/bigdata-venv/bin/python -m pip install pyspark==4.2.0
bash run_hdfs_smoke_wsl.sh
```

Lệnh smoke đưa `fixtures/flights_smoke.csv` (6 dòng tổng hợp, có 1 chuyến bị hủy) vào HDFS, rồi Spark đọc từ `hdfs://127.0.0.1:9000` và ghi hai bảng Parquet trở lại HDFS. Chỉ dùng mẫu này để chứng minh kết nối; không đại diện cho khả năng xử lý 11,2 GB ở máy local.

Hãy chạy các lệnh HDFS trong **cùng cửa sổ Ubuntu và giữ cửa sổ đó mở**. Khi một lệnh `wsl -d Ubuntu -- ...` ngắn chạy xong từ PowerShell, WSL có thể đóng daemon nền. Sau khi mở lại Ubuntu, chạy lại `bash setup_hdfs_wsl.sh` để khởi động dịch vụ; script không format lại NameNode đã có dữ liệu.

Với cluster Hadoop thật và CSV gốc đã có trên HDFS:

```bash
spark-submit hdfs_spark_job.py \
  --input hdfs://namenode:9000/airport/raw/airline.csv \
  --output hdfs://namenode:9000/airport/gold/run-2008
```

Mặc định job không ghi đè output. Chỉ thêm `--overwrite` khi chắc chắn muốn thay thế thư mục đầu ra.

## Đầu nối luồng chuyến bay Aviationstack

Đăng ký API key tại Aviationstack, sau đó đặt biến môi trường trong Ubuntu WSL trước khi mở dashboard:

```bash
export AVIATIONSTACK_API_KEY="thay_bang_api_key_cua_ban"
~/bigdata-venv/bin/python -m streamlit run app.py
```

Trong tab `Luồng chuyến bay`, chọn sân bay và bấm **Lấy dữ liệu trực tiếp**. Dashboard không tự gọi API định kỳ để tránh tiêu hao hạn mức miễn phí. Dữ liệu trả về được đổi sang schema của mô hình, khoảng cách được tính theo tọa độ sân bay và mật độ được đếm trong từng khung 30 phút của snapshot. Chuyến bị hủy hoặc tuyến chưa có tọa độ trong `data/airport_locations.csv` sẽ bị bỏ qua và số lượng được thông báo trên giao diện.

Nếu không cấu hình API, tab vẫn đọc `data/live_flights.csv` làm nguồn dự phòng. CSV cần các cột:

```text
flight_id,scheduled_local,carrier,origin,dest,distance,departure_density_30m
```

`scheduled_local` có dạng `YYYY-MM-DD HH:MM` theo giờ địa phương của sân bay đi. `departure_density_30m` là số chuyến dự kiến trong cùng khung 30 phút và phải do nguồn dữ liệu cung cấp. Ứng dụng **không giả lập** chuyến bay trực tiếp. Mô hình học từ năm 2008 nên dữ liệu hiện nay có thể lệch phân phối; cần kiểm định lại trước khi dùng vận hành thực tế.

## Hạn chế mô hình

R² chỉ khoảng 0,20. MAE với chuyến có TaxiOut trên 60 phút là 58,83 phút, nên mô hình không đáng tin cho sự cố tắc nghẽn hiếm. Chưa có thời tiết, trạng thái đường băng, hàng đợi hay dữ liệu ATC. Xem `MODEL_EVALUATION.md`.
