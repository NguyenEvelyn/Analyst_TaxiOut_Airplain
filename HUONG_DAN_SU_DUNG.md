# Hướng dẫn cài đặt, sử dụng và kiểm tra dữ liệu

Tài liệu này hướng dẫn chạy dự án **Phân tích và dự đoán TaxiOut của chuyến bay** trên Ubuntu WSL. Đây là môi trường đã được dùng để kiểm tra mô hình H2O binary và HDFS local.

## 1. Chức năng chính

Dự án gồm các thành phần:

- Dashboard Streamlit trực quan hóa kết quả phân tích và đánh giá mô hình.
- Mô hình H2O AutoML GLM dự đoán thời gian TaxiOut.
- Dữ liệu thống kê lịch sử dùng để tạo đặc trưng cho mô hình.
- Đầu nối Aviationstack để lấy snapshot chuyến bay bên ngoài.
- Spark job đọc CSV từ HDFS và ghi kết quả dưới dạng Parquet.
- Các chương trình kiểm tra dữ liệu, mô hình và luồng dự đoán.

## 2. Yêu cầu môi trường

- Windows 10/11 có Ubuntu WSL, hoặc Ubuntu Linux.
- Python 3.10 trở lên.
- Java tương thích với H2O và Hadoop.
- Kết nối Internet khi cài thư viện hoặc gọi Aviationstack.
- Git để tải mã nguồn.

HDFS là chức năng mở rộng. Có thể chạy dashboard và mô hình mà không cần khởi động HDFS.

## 3. Tải dự án

Trong Ubuntu WSL:

```bash
git clone https://github.com/NguyenEvelyn/Analyst_TaxiOut_Airplain.git
cd Analyst_TaxiOut_Airplain
```

Nếu làm việc trực tiếp trong thư mục OneDrive hiện tại:

```bash
cd "/mnt/c/Users/Phuong Uyen/OneDrive/Documents/ChatGPT/BigData"
```

## 4. Tạo môi trường Python

```bash
sudo apt update
sudo apt install -y python3 python3-venv default-jre
python3 -m venv ~/bigdata-venv
source ~/bigdata-venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Kiểm tra Java và Python:

```bash
java -version
python --version
python -c "import h2o, pandas, streamlit, plotly; print('Thư viện đã sẵn sàng')"
```

## 5. Kiểm tra các tệp dữ liệu bắt buộc

Chạy từ thư mục gốc của dự án:

```bash
test -f taxiout_deployment_v3/h2o_taxiout_model && echo "OK: H2O model"
test -f taxiout_deployment_v3/metadata.json && echo "OK: metadata"
test -f taxiout_deployment_v3/origin_hour_hist.csv && echo "OK: origin-hour history"
test -f taxiout_deployment_v3/route_hist.csv && echo "OK: route history"
test -f taxiout_deployment_v3/carrier_origin_hist.csv && echo "OK: carrier-origin history"
test -f data/model_comparison_v3.csv && echo "OK: model comparison"
test -f data/error_by_airport_v3.csv && echo "OK: airport errors"
test -f data/error_by_taxi_band_v3.csv && echo "OK: taxi-band errors"
```

Kiểm tra nhanh tên cột và số dòng của các bảng CSV:

```bash
python - <<'PY'
from pathlib import Path
import pandas as pd

folders = [Path("data"), Path("taxiout_deployment_v3"), Path("fixtures")]
for folder in folders:
    for path in sorted(folder.glob("*.csv")):
        frame = pd.read_csv(path)
        print(f"{path}: {len(frame):,} dòng | {len(frame.columns)} cột")
        print("  ", ", ".join(frame.columns))
PY
```

Kết quả không được xuất hiện lỗi `FileNotFoundError`, `ParserError` hoặc lỗi thiếu cột. Không sửa tên cột trong các CSV triển khai nếu chưa cập nhật mã nguồn tương ứng.

## 6. Kiểm tra mô hình H2O

```bash
source ~/bigdata-venv/bin/activate
python test_h2o_local.py
```

Kết quả cần hiển thị:

```text
MODEL_ID: GLM_1_AutoML_2_20261002_33511
PREDICTED_TAXI_OUT_MINUTES: ...
```

Giá trị dự đoán có thể chênh lệch rất nhỏ giữa các môi trường, nhưng phải là một số phút hợp lệ và chương trình không được chuyển sang công thức dự phòng.

Kiểm tra toàn bộ luồng CSV → chuẩn hóa đặc trưng → mô hình H2O:

```bash
python test_live_feed_local.py
```

Kết quả cần có `FEED_TEST_ROWS: 1`, đúng model ID và một giá trị dự đoán.

## 7. Chạy kiểm thử dữ liệu

Dự án dùng `unittest`, do đó không bắt buộc cài pytest:

```bash
python -m unittest discover -s tests -v
```

Các kiểm thử xác nhận:

- Bảng thống kê theo sân bay–giờ có dữ liệu hợp lệ.
- CSV chuyến bay bên ngoài có đủ schema cần thiết.
- Dữ liệu thiếu `departure_density_30m` bị từ chối.
- Payload Aviationstack được chuẩn hóa đúng.

## 8. Chạy dashboard

```bash
source ~/bigdata-venv/bin/activate
python -m streamlit run app.py
```

Mở địa chỉ sau trên trình duyệt:

```text
http://localhost:8501
```

Dashboard gồm năm phần:

1. So sánh các mô hình trên tập kiểm tra.
2. Phân tích sân bay và khung giờ tắc nghẽn.
3. Nhập thông tin chuyến bay để dự đoán TaxiOut.
4. Phân tích sai số theo sân bay và nhóm TaxiOut.
5. Lấy snapshot chuyến bay bên ngoài và thực hiện dự đoán.

Tại phần dự đoán, kiểm tra dòng nguồn mô hình. Dòng này phải chứa:

```text
H2O AutoML — GLM_1_AutoML_2_20261002_33511
```

Nếu giao diện báo đang dùng công thức dự phòng, cần kiểm tra lại Java, phiên bản `h2o` và các tệp trong `taxiout_deployment_v3`.

## 9. Sử dụng Aviationstack

Đăng ký API key trên Aviationstack. Không ghi key trực tiếp vào mã nguồn hoặc commit lên GitHub.

Trong Ubuntu WSL:

```bash
export AVIATIONSTACK_API_KEY="API_KEY_CUA_BAN"
python -m streamlit run app.py
```

Trong tab **Luồng chuyến bay**, chọn sân bay và bấm **Lấy dữ liệu trực tiếp**. Ứng dụng chỉ gọi API khi người dùng bấm nút nhằm hạn chế tiêu hao quota.

Nếu không có API key, ứng dụng có thể dùng `data/live_flights.csv` làm nguồn dự phòng. File này cần các cột:

```text
flight_id,scheduled_local,carrier,origin,dest,distance,departure_density_30m
```

Trong đó:

- `scheduled_local`: thời gian địa phương, dạng `YYYY-MM-DD HH:MM`.
- `carrier`, `origin`, `dest`: mã IATA.
- `distance`: khoảng cách tính bằng mile.
- `departure_density_30m`: số chuyến trong cùng khung 30 phút.

## 10. Chạy HDFS và Spark smoke test

Phần này tạo HDFS pseudo-distributed một nút để kiểm chứng kết nối. Nó không phải cluster Hadoop sản xuất.

```bash
source ~/bigdata-venv/bin/activate
python -m pip install pyspark==4.2.0
bash setup_hdfs_wsl.sh
bash run_hdfs_smoke_wsl.sh
```

Giữ cùng cửa sổ Ubuntu mở trong suốt quá trình. Kết quả thành công sẽ hiển thị đường dẫn tương tự:

```text
HDFS_SPARK_SMOKE_OUTPUT=hdfs://127.0.0.1:9000/airport/gold/smoke-...
```

Kiểm tra trạng thái HDFS:

```bash
hdfs dfsadmin -report
hdfs dfs -ls /airport/raw/smoke
hdfs dfs -ls /airport/gold
```

Với dữ liệu thật đã có trên một cluster Hadoop:

```bash
spark-submit hdfs_spark_job.py \
  --input hdfs://namenode:9000/airport/raw/airline.csv \
  --output hdfs://namenode:9000/airport/gold/run-2008
```

Job mặc định không ghi đè thư mục output. Chỉ dùng `--overwrite` khi chắc chắn muốn thay thế kết quả cũ.

## 11. Kiểm tra trước khi báo cáo hoặc demo

Chạy lần lượt:

```bash
python -m unittest discover -s tests -v
python test_h2o_local.py
python test_live_feed_local.py
python -m streamlit run app.py
```

Sau đó xác nhận:

- Dashboard mở được ở cổng 8501.
- Các bảng và biểu đồ chính hiển thị dữ liệu.
- Model ID đúng với metadata.
- Dự đoán trả về số phút hợp lệ.
- Không có API key hoặc thông tin bí mật trong mã nguồn.

## 12. Lỗi thường gặp

### Không tìm thấy lệnh `python`

Kích hoạt môi trường:

```bash
source ~/bigdata-venv/bin/activate
```

Hoặc thay `python` bằng `python3`.

### H2O không khởi động

Kiểm tra Java:

```bash
java -version
```

Sau đó xác nhận phiên bản Python package:

```bash
python -c "import h2o; print(h2o.__version__)"
```

Dự án sử dụng H2O `3.46.0.11`.

### Dashboard thiếu biểu đồ theo giờ

Khi không có `data/hourly_congestion_top20.csv`, ứng dụng sử dụng dữ liệu lịch sử tháng 1–9/2008 trong `origin_hour_hist.csv`. Nếu không có `error_by_hour_v3.csv`, biểu đồ MAE theo giờ được để trống thay vì nội suy số liệu.

### HDFS không chạy sau khi đóng WSL

Mở lại Ubuntu và chạy:

```bash
bash setup_hdfs_wsl.sh
```

Script sẽ khởi động lại dịch vụ và không format lại NameNode đã có dữ liệu.

## 13. Giới hạn sử dụng

- Mô hình học từ dữ liệu năm 2008 nên có thể lệch phân phối so với chuyến bay hiện nay.
- R² khoảng 0,20; mô hình không nên được dùng độc lập cho quyết định khai thác thực tế.
- Sai số cao đối với các sự kiện tắc nghẽn hiếm, đặc biệt khi TaxiOut trên 60 phút.
- Mô hình chưa có thời tiết, trạng thái đường băng, loại tàu bay, hàng đợi hoặc dữ liệu ATC.
- HDFS local chỉ dùng để học tập và kiểm chứng pipeline.

Xem thêm kết quả chi tiết trong `MODEL_EVALUATION.md` và mô tả tổng quan trong `README.md`.
