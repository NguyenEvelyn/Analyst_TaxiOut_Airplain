# Đánh giá mô hình dự đoán TaxiOut

## Thiết kế đánh giá

Dữ liệu được chia theo thời gian để hạn chế rò rỉ dữ liệu: tháng 1-9/2008 dùng huấn luyện, tháng 10 dùng validation và tháng 11-12 dùng kiểm tra. Mô hình cải thiện sử dụng 450.000 dòng train, 140.000 dòng validation và 180.000 dòng test.

## Kết quả

| Mô hình | MAE (phút) | RMSE (phút) | R² | Cải thiện MAE |
|---|---:|---:|---:|---:|
| Global mean | 7,1996 | 11,2929 | -0,0008 | 0,00% |
| Trung bình lịch sử Origin-Hour | 6,2215 | 10,3018 | 0,1672 | 13,58% |
| H2O AutoML enhanced | **5,8445** | **10,0755** | **0,2034** | **18,82%** |

## Diễn giải

- MAE 5,84 phút nghĩa là dự đoán lệch trung bình khoảng 5,84 phút so với TaxiOut thực tế.
- RMSE 10,08 phút cao hơn MAE đáng kể, cho thấy vẫn có một nhóm chuyến bay có sai số lớn.
- R² 0,2034 cho thấy mô hình giải thích khoảng 20,34% biến động TaxiOut trên dữ liệu tương lai theo thời gian.
- Mô hình H2O AutoML giảm MAE khoảng 18,82% so với baseline Global Mean và tốt hơn thống kê lịch sử Origin-Hour.

## Kết luận

Mô hình đạt yêu cầu của đề tài về xây dựng pipeline Spark–H2O AutoML, so sánh mô hình và dự đoán TaxiOut. Kết quả phù hợp để hỗ trợ phân tích tắc nghẽn, xếp hạng sân bay và cảnh báo vận hành. Tuy nhiên, mô hình chưa nên dùng độc lập cho quyết định khai thác thời gian thực vì dữ liệu chưa có thời tiết, cấu hình đường băng, hàng đợi lăn, loại tàu bay và trạng thái ATC.

## Phân tích sai số chi tiết

Mô hình hoạt động tốt nhất với các chuyến có TaxiOut từ 11–20 phút, MAE khoảng 3,78 phút. Sai số tăng lên 18,06 phút với nhóm TaxiOut 31–60 phút và 58,83 phút với nhóm trên 60 phút. Bias dương rất lớn ở hai nhóm này cho thấy mô hình thường dự đoán thấp hơn thực tế đối với các sự kiện tắc nghẽn bất thường.

Ba sân bay có MAE cao nhất trong tập kiểm tra là JFK (13,50 phút), LGA (11,46 phút) và EWR (10,90 phút). Đây đều là các sân bay khu vực New York có vận hành phức tạp, vì vậy cần thêm dữ liệu thời tiết, đường băng và ATC nếu muốn cải thiện dự báo tại các sân bay này.

## Hướng cải thiện

1. Bổ sung thời tiết, loại tàu bay, đường băng và dữ liệu ATC.
2. Dùng đặc trưng trượt 30-60 phút chỉ từ dữ liệu quá khứ.
3. Đánh giá MAE riêng theo sân bay, giờ cao điểm và nhóm TaxiOut.
4. Đã xuất mô hình H2O binary và kiểm tra dự đoán local trong WSL. Nếu cần triển khai không phụ thuộc H2O server, có thể nghiên cứu MOJO như một hướng tiếp theo.
