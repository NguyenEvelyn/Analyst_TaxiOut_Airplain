from pathlib import Path
import hashlib
import json
import os

import pandas as pd
import plotly.express as px
import streamlit as st

from batch_analysis import evaluation, parse_upload, predict_batch
from h2o_predictor import H2OTaxiOutPredictor, deployment_is_ready
from dashboard_data import training_hourly_profile
from live_feed import (
    REQUIRED_COLUMNS,
    LiveFeedError,
    fetch_aviationstack_feed,
    read_live_feed,
    to_prediction_kwargs,
)


ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
MODEL_DIR = ROOT / "taxiout_deployment_v3"

st.set_page_config(page_title="Airport Taxi Time", page_icon="✈️", layout="wide")
st.markdown("""
<style>
  :root { --airport-blue: #1e40af; --airport-amber: #b45309; }
  .block-container { max-width: 1420px; padding-top: 2rem; padding-bottom: 3rem; }
  h1, h2, h3 { letter-spacing: -.025em; }
  [data-testid="stMetric"] { background: #f8fafc; border: 1px solid #dbeafe;
      border-radius: 12px; padding: 16px; min-height: 110px; }
  [data-testid="stMetricLabel"] { color: #334155; }
  [data-testid="stTabs"] button { min-height: 48px; }
  .airport-hero { border-left: 5px solid var(--airport-blue); background: #f8fafc;
      padding: 18px 22px; border-radius: 10px; margin-bottom: 22px; }
  .airport-hero p { margin: 0; color: #334155; }
  @media (max-width: 700px) { .block-container { padding: 1rem; }
      .airport-hero { padding: 14px; } }
</style>
""", unsafe_allow_html=True)
st.title("Phân tích vận hành sân bay & TaxiOut")
st.markdown("<div class='airport-hero'><p>Dữ liệu chuyến bay 2008 · Spark xử lý · H2O AutoML dự đoán · Plotly trực quan hóa</p></div>", unsafe_allow_html=True)


@st.cache_data
def read_csv(name: str) -> pd.DataFrame:
    path = DATA_DIR / name
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


@st.cache_data
def read_json(name: str) -> dict:
    path = DATA_DIR / name
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as file:
        return json.load(file)


comparison = read_csv("model_comparison_v3.csv")
airports = read_csv("airport_summary_2008.csv")
hourly = read_csv("hourly_congestion_top20.csv")
locations = read_csv("airport_locations.csv")
error_airport = read_csv("error_by_airport_v3.csv")
error_hour = read_csv("error_by_hour_v3.csv")
error_band = read_csv("error_by_taxi_band_v3.csv")
leaderboard = read_csv("h2o_leaderboard_v3.csv")
coefficients = read_csv("glm_coefficients_v3.csv")
confidence = read_json("model_confidence_v3.json")


@st.cache_resource
def load_h2o_predictor(model_dir: str) -> H2OTaxiOutPredictor:
    return H2OTaxiOutPredictor(Path(model_dir))


model_ready = deployment_is_ready(MODEL_DIR)
hourly_is_training_profile = False
if hourly.empty and model_ready and not airports.empty:
    hourly = training_hourly_profile(MODEL_DIR, airports["Origin"].tolist())
    hourly_is_training_profile = True

required_files = {
    "So sánh mô hình": DATA_DIR / "model_comparison_v3.csv",
    "Tổng hợp sân bay": DATA_DIR / "airport_summary_2008.csv",
}

with st.sidebar:
    st.header("Trạng thái dữ liệu")
    for label, path in required_files.items():
        st.write(f"{'✅' if path.exists() else '⚠️'} {label}")
    if hourly_is_training_profile:
        st.write("ℹ️ Theo giờ: dữ liệu huấn luyện tháng 1–9/2008")
    else:
        st.write(f"{'✅' if not hourly.empty else '⚠️'} Tắc nghẽn theo giờ cả năm")
    st.write(f"{'✅' if model_ready else '⚠️'} Tệp mô hình H2O")
    st.caption("Tệp CSV thật được đọc từ thư mục data. Số liệu mẫu chỉ dùng khi chưa có tệp tương ứng.")

tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "Hiệu năng mô hình", "Tắc nghẽn sân bay", "Dự đoán TaxiOut", "Phân tích sai số",
    "Luồng chuyến bay", "Tải CSV & đánh giá"
])

with tab1:
    st.subheader("So sánh mô hình trên tập kiểm tra theo thời gian")
    if comparison.empty:
        comparison = pd.DataFrame(
            [
                ["Global mean", 7.198947, 11.292029, -0.000757, 0.0],
                ["Origin-hour historical mean", 6.220556, 10.300605, 0.167259, 13.590751],
                ["H2O AutoML enhanced", 5.841377, 10.075190, 0.203307, 18.857906],
            ],
            columns=["model", "MAE", "RMSE", "R2", "MAE_improvement_vs_global_pct"],
        )
        st.info("Đang hiển thị kết quả đã ghi nhận từ notebook. Chép CSV vào thư mục data để cập nhật tự động.")

    c1, c2, c3 = st.columns(3)
    best = comparison.loc[comparison["RMSE"].idxmin()]
    c1.metric("Mô hình tốt nhất", best["model"])
    c2.metric("MAE", f"{best['MAE']:.2f} phút")
    c3.metric("RMSE", f"{best['RMSE']:.2f} phút")
    d1, d2 = st.columns(2)
    d1.metric("R²", f"{best['R2']:.3f}")
    d2.metric("Cải thiện MAE so với global mean",
              f"{best.get('MAE_improvement_vs_global_pct', 0):.2f}%")
    melted = comparison.melt(id_vars="model", value_vars=["MAE", "RMSE"],
                              var_name="metric", value_name="minutes")
    st.plotly_chart(px.bar(melted, x="model", y="minutes", color="metric", barmode="group",
                           title="MAE và RMSE — thấp hơn là tốt hơn"), width="stretch")
    st.dataframe(comparison, width="stretch", hide_index=True)
    if confidence:
        st.write(
            "**Độ bất định trên tập kiểm tra:** "
            f"MAE bootstrap 95% CI = {confidence['ci95_lower']:.2f}–"
            f"{confidence['ci95_upper']:.2f} phút; "
            f"sai số ≤5 phút: {confidence.get('within_5_minutes_pct', 0):.1f}%, "
            f"≤10 phút: {confidence.get('within_10_minutes_pct', 0):.1f}%."
        )
    else:
        st.caption("Chưa có model_confidence_v3.json; chạy BƯỚC 13 để tạo khoảng tin cậy bootstrap.")
    if not leaderboard.empty:
        with st.expander("Leaderboard H2O AutoML"):
            st.dataframe(leaderboard, width="stretch", hide_index=True)
    if not coefficients.empty:
        with st.expander("Hệ số mô hình GLM"):
            st.dataframe(coefficients.head(30), width="stretch", hide_index=True)
    with st.expander("Cách đọc các chỉ số", expanded=True):
        st.markdown(
            """
            - **MAE** là sai lệch tuyệt đối trung bình. MAE khoảng 5,84 nghĩa là dự đoán thường lệch gần 6 phút.
            - **RMSE** phạt mạnh các trường hợp sai số lớn. RMSE khoảng 10 phút cho thấy vẫn tồn tại chuyến bay khó dự đoán.
            - **R²** khoảng 0,20 nghĩa là mô hình giải thích gần 20% biến thiên TaxiOut trên tập kiểm tra theo thời gian.
            - Kết quả phù hợp cho **phân tích và cảnh báo vận hành**, nhưng chưa đủ để xem là dự báo chính xác cao trong môi trường khai thác thật.
            """
        )

with tab2:
    st.subheader("Sân bay và khung giờ quá tải")
    if airports.empty:
        airports = pd.DataFrame(
            [
                ["ORD", 334487, 19.15, 33.68, 11809], ["LAX", 212292, 15.04, 25.90, 11383],
                ["ATL", 407546, 19.90, 31.82, 11284], ["DFW", 273305, 15.86, 25.38, 11266],
                ["JFK", 114877, 33.26, 48.99, 10896], ["DEN", 238188, 15.58, 25.26, 9914],
                ["EWR", 133542, 28.21, 43.48, 9469], ["LGA", 113023, 27.56, 42.58, 8649],
            ], columns=["Origin", "total_flights", "avg_taxi_out", "avg_p95_taxi_out", "overloaded_windows"])
    top_n = st.slider("Số sân bay", 5, min(30, len(airports)), min(15, len(airports)))
    view = airports.nlargest(top_n, "overloaded_windows")
    st.plotly_chart(px.bar(view, x="Origin", y="overloaded_windows", color="avg_taxi_out",
                           title="Số cửa sổ 30 phút quá tải",
                           labels={"Origin": "Sân bay", "overloaded_windows": "Cửa sổ quá tải",
                                   "avg_taxi_out": "TaxiOut TB"}), width="stretch")
    st.dataframe(view, width="stretch", hide_index=True)
    if not locations.empty:
        map_df = airports.merge(locations, on="Origin", how="inner")
        st.plotly_chart(
            px.scatter_map(
                map_df,
                lat="latitude",
                lon="longitude",
                size="total_flights",
                color="avg_taxi_out",
                hover_name="Origin",
                hover_data={
                    "total_flights": ":,",
                    "avg_taxi_out": ":.2f",
                    "overloaded_windows": ":,",
                    "latitude": False,
                    "longitude": False,
                },
                zoom=2.5,
                center={"lat": 38.5, "lon": -97.0},
                title="Bản đồ hiệu năng các sân bay Hoa Kỳ",
                labels={"avg_taxi_out": "TaxiOut TB"},
            ),
            width="stretch",
        )
    if not hourly.empty:
        airport = st.selectbox("Xem theo giờ", sorted(hourly["Origin"].unique()))
        airport_hourly = hourly[hourly["Origin"] == airport].sort_values("dep_hour")
        if hourly_is_training_profile:
            st.info("Biểu đồ theo giờ lấy từ tập huấn luyện tháng 1–9/2008; không phải số cửa sổ quá tải cả năm.")
        st.plotly_chart(px.line(airport_hourly, x="dep_hour", y="avg_taxi_out", markers=True,
                                title=f"TaxiOut trung bình theo giờ — {airport}"), width="stretch")
        if hourly_is_training_profile:
            st.plotly_chart(px.bar(airport_hourly, x="dep_hour", y="flights",
                                   title=f"Số chuyến theo giờ (tháng 1–9/2008) — {airport}"),
                            width="stretch")
    else:
        st.info("Chép hourly_congestion_top20.csv từ Kaggle vào thư mục data để bật biểu đồ theo giờ.")

with tab3:
    st.subheader("Dự đoán TaxiOut")
    if model_ready:
        st.success("Đã có gói mô hình H2O từ Kaggle; mô hình sẽ được nạp khi bấm Dự đoán.")
    else:
        st.warning("Chưa có gói mô hình local; ứng dụng đang dùng công thức ước lượng dự phòng.")
    a, b, c = st.columns(3)
    origin = a.selectbox("Sân bay đi", sorted(airports["Origin"].unique()))
    dep_hour = b.slider("Giờ khởi hành", 0, 23, 8)
    density = c.number_input("Số chuyến trong 30 phút", 1, 200, 70)
    dep_minute = b.selectbox("Phút", [0, 15, 30, 45], index=2)
    distance = c.number_input("Khoảng cách (mile)", 20, 5000, 761)
    month = a.slider("Tháng", 1, 12, 12)
    day = b.slider("Ngày trong tháng", 1, 31, 15)
    day_of_week = c.slider("Thứ (1=Thứ hai, 7=Chủ nhật)", 1, 7, 1)
    carrier = a.text_input("Hãng bay", "DL").strip().upper()
    dest = b.text_input("Sân bay đến", "LGA").strip().upper()
    is_peak = int(dep_hour in [7, 8, 9, 16, 17, 18, 19])
    airport_mean = float(airports.loc[airports["Origin"] == origin, "avg_taxi_out"].iloc[0])
    estimate = max(3.0, airport_mean + 0.055 * density + 1.5 * is_peak + 0.0002 * distance - 3.0)
    if st.button("Dự đoán", type="primary"):
        prediction = estimate
        source = "công thức ước lượng dự phòng"
        if model_ready:
            try:
                predictor = load_h2o_predictor(str(MODEL_DIR))
                for warning in predictor.assess_input(
                    carrier=carrier,
                    origin=origin,
                    dest=dest,
                    departure_density=density,
                ):
                    st.warning(f"Cảnh báo phạm vi mô hình: {warning}.")
                prediction = predictor.predict(
                    month=month, day=day, day_of_week=day_of_week,
                    dep_hour=dep_hour, dep_minute=dep_minute, carrier=carrier,
                    origin=origin, dest=dest, distance=distance,
                    departure_density=density,
                )
                source = f"H2O AutoML — {predictor.model_id}"
            except Exception as exc:
                st.error(f"Không nạp được mô hình H2O: {exc}")
                st.info("Đang trả về ước lượng dự phòng để dashboard không bị gián đoạn.")
        st.metric("TaxiOut dự đoán", f"{prediction:.1f} phút")
        level = "Quá tải" if prediction >= 30 else "Cao" if prediction >= 22 else "Trung bình" if prediction >= 15 else "Thấp"
        st.write(f"Mức tắc nghẽn ước lượng: **{level}**")
        st.caption(f"Nguồn dự đoán: {source}")

with tab4:
    st.subheader("Mô hình sai nhiều nhất ở đâu?")
    if error_airport.empty and error_hour.empty and error_band.empty:
        st.info(
            "Chạy BƯỚC 13 trong file kaggle_steps_12_13.py trên Kaggle, sau đó tải ba tệp "
            "error_by_airport_v3.csv, error_by_hour_v3.csv và error_by_taxi_band_v3.csv vào thư mục data."
        )
        st.markdown(
            "Phân tích này giúp kiểm tra mô hình có yếu ở sân bay nào, giờ nào và với các chuyến TaxiOut dài hay không."
        )
    if not error_hour.empty:
        st.plotly_chart(
            px.line(error_hour.sort_values("dep_hour"), x="dep_hour", y="MAE", markers=True,
                    title="MAE theo giờ khởi hành",
                    labels={"dep_hour": "Giờ", "MAE": "MAE (phút)"}),
            width="stretch",
        )
    else:
        st.info("Chưa có error_by_hour_v3.csv từ Kaggle; không thể suy ra MAE theo giờ từ các bảng còn lại.")
    if not error_band.empty:
        st.plotly_chart(
            px.bar(error_band, x="actual_band", y="MAE", color="bias",
                   title="Sai số theo nhóm TaxiOut thực tế",
                   labels={"actual_band": "TaxiOut thực tế", "MAE": "MAE (phút)", "bias": "Độ lệch"}),
            width="stretch",
        )
    if not error_airport.empty:
        st.dataframe(error_airport.head(20), width="stretch", hide_index=True)

with tab5:
    st.subheader("Theo dõi chuyến bay bên ngoài")
    st.caption(
        "Lấy snapshot chuyến bay hiện tại từ Aviationstack hoặc đọc CSV dự phòng. "
        "Mô hình học từ dữ liệu năm 2008 nên kết quả chỉ phục vụ thử nghiệm."
    )
    st.code(",".join(REQUIRED_COLUMNS), language="text")

    configured_key = os.getenv("AVIATIONSTACK_API_KEY", "")
    live_origin = st.selectbox("Sân bay đi cần theo dõi", sorted(locations["Origin"].unique()), key="live_origin")
    api_key = st.text_input(
        "Aviationstack API key",
        value=configured_key,
        type="password",
        help="Nên đặt biến môi trường AVIATIONSTACK_API_KEY; khóa chỉ được dùng cho lần gọi API này.",
    )
    if st.button("Lấy dữ liệu trực tiếp", type="primary"):
        try:
            with st.spinner("Đang lấy snapshot từ Aviationstack..."):
                live_snapshot = fetch_aviationstack_feed(api_key, live_origin, locations)
            st.session_state["aviationstack_feed"] = live_snapshot
            st.session_state["aviationstack_origin"] = live_origin
            st.session_state["aviationstack_source_count"] = live_snapshot.attrs.get("source_count", 0)
        except LiveFeedError as exc:
            st.error(str(exc))

    def show_live_feed() -> None:
        feed = st.session_state.get("aviationstack_feed", pd.DataFrame())
        source = "Aviationstack"
        if feed.empty:
            feed_path = DATA_DIR / "live_flights.csv"
            try:
                feed = read_live_feed(feed_path)
                source = "CSV local"
            except (ValueError, OSError) as exc:
                st.error(f"CSV luồng chuyến bay không hợp lệ: {exc}")
                return
        if feed.empty:
            st.info("Nhập API key và bấm Lấy dữ liệu trực tiếp, hoặc đặt data/live_flights.csv để dùng nguồn dự phòng.")
            return
        if not model_ready:
            st.error("Chưa có mô hình H2O; không thể dự đoán luồng chuyến bay.")
            return
        if source == "Aviationstack":
            total = st.session_state.get("aviationstack_source_count", len(feed))
            st.write(
                f"Aviationstack trả về {total} bản ghi; dùng được {len(feed)} chuyến có đủ tọa độ và đặc trưng. "
                "Hiển thị tối đa 10 chuyến mới nhất."
            )
        else:
            st.write(f"Đã đọc {len(feed)} chuyến từ CSV. Hiển thị tối đa 10 chuyến mới nhất.")
        recent = feed.tail(10).copy()
        try:
            predictor = load_h2o_predictor(str(MODEL_DIR))
            recent["predicted_taxi_out_minutes"] = [
                predictor.predict(**to_prediction_kwargs(row))
                for _, row in recent.iterrows()
            ]
        except Exception as exc:
            st.error(f"Dự đoán H2O thất bại: {exc}")
            return
        st.dataframe(recent, width="stretch", hide_index=True)
        st.caption(f"Nguồn chuyến bay: {source} · Nguồn dự đoán: H2O AutoML — {predictor.model_id}")

    show_live_feed()

with tab6:
    st.subheader("Dự đoán hàng loạt từ CSV")
    st.write(
        "Tải lịch bay lên để dự đoán TaxiOut. Nếu tệp có thêm cột `TaxiOut` thực tế, "
        "hệ thống sẽ tính sai số trên các dòng có nhãn. Tệp tải lên không dùng để huấn luyện lại."
    )
    with st.expander("Định dạng CSV cần chuẩn bị", expanded=True):
        st.code(
            "flight_id,scheduled_local,carrier,origin,dest,distance,departure_density_30m,TaxiOut\n"
            "DL123,2008-11-15 08:30,DL,ATL,LGA,761,30,22",
            language="text",
        )
        st.caption(
            "TaxiOut là cột tùy chọn. scheduled_local dùng giờ địa phương của sân bay đi; "
            "distance tính bằng mile. Mật độ 30 phút phải đến từ lịch bay đầy đủ, không phải "
            "số dòng ngẫu nhiên trong tệp mẫu. Giới hạn: 10 MB và 2.000 chuyến/lần."
        )
    uploaded = st.file_uploader("Chọn tệp CSV UTF-8", type="csv", key="batch_upload")
    if uploaded is not None:
        upload_bytes = uploaded.getvalue()
        upload_digest = hashlib.sha256(upload_bytes).hexdigest()
        try:
            batch_input = parse_upload(upload_bytes)
        except ValueError as exc:
            st.error(str(exc))
        else:
            c1, c2, c3 = st.columns(3)
            c1.metric("Chuyến hợp lệ", f"{len(batch_input):,}")
            c2.metric("Sân bay đi", batch_input["origin"].nunique())
            c3.metric("Có TaxiOut thực tế", int(batch_input.get("TaxiOut", pd.Series(dtype=float)).notna().sum()))
            st.dataframe(batch_input.head(20), width="stretch", hide_index=True)
            if not model_ready:
                st.error("Chưa có gói mô hình H2O local; không thể dự đoán hàng loạt.")
            elif st.button("Chạy dự đoán hàng loạt", type="primary"):
                try:
                    with st.spinner(f"H2O đang dự đoán {len(batch_input):,} chuyến..."):
                        predictor = load_h2o_predictor(str(MODEL_DIR))
                        result = predict_batch(predictor, batch_input)
                    st.session_state["batch_result"] = result
                    st.session_state["batch_digest"] = upload_digest
                    st.session_state["batch_model_id"] = predictor.model_id
                except Exception as exc:
                    st.error(f"Không hoàn tất dự đoán H2O: {exc}")
                    st.info("Kiểm tra các giá trị ngày giờ, mã sân bay và trạng thái H2O rồi thử lại.")

    result = st.session_state.get("batch_result")
    if result is not None and uploaded is not None and st.session_state.get("batch_digest") == upload_digest:
        st.divider()
        st.subheader("Kết quả dự đoán")
        st.caption(f"Mô hình: H2O AutoML — {st.session_state['batch_model_id']} · Không huấn luyện lại")
        scores = evaluation(result)
        if scores:
            a, b, c, d = st.columns(4)
            a.metric("Dòng có nhãn", f"{scores['count']:,}")
            b.metric("MAE", f"{scores['mae']:.2f} phút")
            c.metric("RMSE", f"{scores['rmse']:.2f} phút")
            d.metric("Bias (thực tế − dự đoán)", f"{scores['bias']:+.2f} phút")
            st.warning("Các chỉ số này đo trên tệp vừa tải, không thay thế kết quả kiểm tra độc lập của mô hình.")
        else:
            st.info("Không có TaxiOut thực tế nên chỉ hiển thị dự đoán, chưa thể đánh giá độ chính xác.")
        grouped = result.groupby("origin", as_index=False).agg(
            flights=("flight_id", "count"), avg_prediction=("predicted_taxi_out_minutes", "mean")
        ).sort_values("avg_prediction", ascending=False)
        left, right = st.columns([3, 2])
        with left:
            st.plotly_chart(px.bar(grouped.head(15), x="origin", y="avg_prediction",
                hover_data=["flights"], title="TaxiOut dự đoán trung bình theo sân bay đi",
                labels={"origin": "Sân bay đi", "avg_prediction": "Phút"},
                color_discrete_sequence=["#1e40af"]), width="stretch")
        with right:
            st.dataframe(grouped.head(15).round(2), width="stretch", hide_index=True)
        st.dataframe(result, width="stretch", hide_index=True)
        st.download_button("Tải kết quả CSV", result.to_csv(index=False).encode("utf-8-sig"),
                           file_name="taxiout_batch_predictions.csv", mime="text/csv")
