from datetime import datetime
import pandas as pd
import pymysql
from sqlalchemy import create_engine, text
import streamlit as st
st.image("123.jpg")
# =========================================================
# CONFIG & KẾT NỐI DATABASE (LẤY TỪ CẤU HÌNH CỦA BẠN)
# =========================================================

DB_USER = "avnadmin"
DB_PASSWORD = "AVNS_vDsaU2snGWjBZuSHONt"
DB_HOST = "mysql-11e928b1-nbhieuphung2005-1a49.h.aivencloud.com"
DB_PORT = 18185
DB_NAME = "defaultdb"


def make_connection():
    return pymysql.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME,
        charset="utf8mb4",
        autocommit=True,
        connect_timeout=30,
        ssl_verify_cert=False,
    )


@st.cache_resource
def get_db():
    return create_engine(
        f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}",
        creator=make_connection,
        pool_pre_ping=True,
        pool_recycle=1800,
    )


DB = get_db()


def execute_sql(query, params=None):
    with DB.begin() as conn:
        return conn.execute(text(query), params or {})


def read_df(query, params=None):
    with DB.connect() as conn:
        return pd.read_sql(text(query), conn, params=params or {})


# =========================================================
# CHỨC NĂNG CHÍNH: THEO DÕI TÌNH HÌNH PHÒNG
# =========================================================


def render_room_tracker_page():
    st.title("🛏️ Theo Dõi Tình Hình Phòng Real-time")
    st.caption("Sơ đồ phòng theo thời gian thực — Quản lý trạng thái, dọn dẹp & bảo trì")

    # 1. TRUY VẤN DỮ LIỆU TỔNG HỢP PHÒNG
    query_rooms = """
        SELECT 
            r.id AS room_id,
            r.room_number,
            r.room_type,
            r.floor,
            r.price,
            r.status AS room_status,
            COALESCE(h.status, 'Sạch') AS hk_status,
            COALESCE(h.staff, 'Chưa phân công') AS hk_staff,
            b.id AS booking_id,
            g.full_name AS guest_name,
            b.check_in,
            b.check_out
        FROM rooms r
        LEFT JOIN housekeeping h ON h.room_id = r.id
        LEFT JOIN bookings b ON b.room_id = r.id AND b.status IN ('Đã đặt', 'Đã check-in')
        LEFT JOIN guests g ON g.id = b.guest_id
        ORDER BY r.floor ASC, r.room_number ASC
    """
    df_rooms = read_df(query_rooms)

    if df_rooms.empty:
        st.warning("⚠️ Chưa có dữ liệu phòng trong cơ sở dữ liệu.")
        return

    # 2. KHU VỰC THỐNG KÊ NHANH (KPI METRICS)
    total_rooms = len(df_rooms)
    vacant_count = len(df_rooms[df_rooms["room_status"] == "Trống"])
    occupied_count = len(df_rooms[df_rooms["room_status"] == "Đang ở"])
    reserved_count = len(df_rooms[df_rooms["room_status"] == "Đã đặt"])
    maint_count = len(df_rooms[df_rooms["room_status"] == "Bảo trì"])
    dirty_count = len(df_rooms[df_rooms["hk_status"].isin(["Cần dọn", "Đang dọn"])])

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("Tổng số phòng", total_rooms)
    c2.metric("🟢 Phòng trống", vacant_count)
    c3.metric("🔴 Đang có khách", occupied_count)
    c4.metric("🟡 Đã đặt trước", reserved_count)
    c5.metric("🔧 Đang bảo trì", maint_count)
    c6.metric("🧹 Cần vệ sinh", dirty_count)

    st.divider()

    # 3. BỘ LỌC TÌM KIẾM & HIỂN THỊ
    col_filter1, col_filter2, col_filter3 = st.columns([1, 1, 1])

    with col_filter1:
        floor_options = ["Tất cả tầng"] + sorted(
            [f"Tầng {f}" for f in df_rooms["floor"].unique()]
        )
        selected_floor = st.selectbox("🏢 Lọc theo Tầng", floor_options)

    with col_filter2:
        status_options = [
            "Tất cả trạng thái",
            "Trống",
            "Đang ở",
            "Đã đặt",
            "Bảo trì",
        ]
        selected_status = st.selectbox("📌 Trạng thái sử dụng", status_options)

    with col_filter3:
        hk_options = [
            "Tất cả vệ sinh",
            "Sạch",
            "Cần dọn",
            "Đang dọn",
            "Đã kiểm tra",
        ]
        selected_hk = st.selectbox("🧹 Trạng thái vệ sinh", hk_options)

    # Áp dụng bộ lọc
    filtered_df = df_rooms.copy()
    if selected_floor != "Tất cả tầng":
        floor_num = int(selected_floor.replace("Tầng ", ""))
        filtered_df = filtered_df[filtered_df["floor"] == floor_num]

    if selected_status != "Tất cả trạng thái":
        filtered_df = filtered_df[filtered_df["room_status"] == selected_status]

    if selected_hk != "Tất cả vệ sinh":
        filtered_df = filtered_df[filtered_df["hk_status"] == selected_hk]

    st.write(f"Đang hiển thị **{len(filtered_df)}** phòng:")

    # 4. HIỂN THỊ SƠ ĐỒ MẶT BẰNG DẠNG LƯỚI (ROOM BOARD GRID)
    # Quy định màu sắc theo trạng thái
    STATUS_COLORS = {
        "Trống": "#28a745",  # Xanh lá
        "Đang ở": "#dc3545",  # Đỏ
        "Đã đặt": "#ffc107",  # Vàng
        "Bảo trì": "#6c757d",  # Xám
    }

    # Hiển thị lưới 4 cột mỗi dòng
    cols_per_row = 4
    floors = filtered_df["floor"].unique()

    for fl in sorted(floors):
        st.subheader(f"🏢 Tầng {fl}")
        floor_rooms = filtered_df[filtered_df["floor"] == fl]

        # Chia dòng thành các cột
        for i in range(0, len(floor_rooms), cols_per_row):
            cols = st.columns(cols_per_row)
            batch = floor_rooms.iloc[i : i + cols_per_row]

            for idx, (_, room) in enumerate(batch.iterrows()):
                color = STATUS_COLORS.get(room["room_status"], "#0d6efd")

                with cols[idx]:
                    # Thẻ thông tin phòng (Card UI)
                    st.markdown(
                        f"""
                        <div style="
                            border: 2px solid {color};
                            border-radius: 10px;
                            padding: 12px;
                            margin-bottom: 10px;
                            background-color: rgba(255, 255, 255, 0.05);
                        ">
                            <h3 style="margin:0; color:{color};">P.{room['room_number']} <small style="font-size:14px; color:#aaa;">({room['room_type']})</small></h3>
                            <p style="margin: 5px 0;"><b>Trạng thái:</b> <span style="color:{color}; font-weight:bold;">{room['room_status']}</span></p>
                            <p style="margin: 5px 0;"><b>Vệ sinh:</b> {room['hk_status']}</p>
                            <p style="margin: 5px 0; font-size:13px; color:#ddd;"><b>Khách:</b> {room['guest_name'] if pd.notna(room['guest_name']) else '---'}</p>
                        </div>
                        """,
                        unsafe_allow_html=True,
                    )

                    # Nút thao tác nhanh trên phòng
                    with st.expander("⚡ Thao tác nhanh"):
                        new_status = st.selectbox(
                            "Đổi trạng thái",
                            ["Trống", "Đang ở", "Đã đặt", "Bảo trì"],
                            index=["Trống", "Đang ở", "Đã đặt", "Bảo trì"].index(
                                room["room_status"]
                            ),
                            key=f"status_{room['room_id']}",
                        )

                        new_hk = st.selectbox(
                            "Đổi trạng thái vệ sinh",
                            ["Sạch", "Cần dọn", "Đang dọn", "Đã kiểm tra"],
                            index=[
                                "Sạch",
                                "Cần dọn",
                                "Đang dọn",
                                "Đã kiểm tra",
                            ].index(room["hk_status"]),
                            key=f"hk_{room['room_id']}",
                        )

                        if st.button(
                            "💾 Lưu thay đổi", key=f"btn_{room['room_id']}"
                        ):
                            # Cập nhật trạng thái phòng
                            execute_sql(
                                "UPDATE rooms SET status=:st WHERE id=:rid",
                                {"st": new_status, "rid": room["room_id"]},
                            )
                            # Cập nhật trạng thái dọn dẹp
                            execute_sql(
                                """
                                INSERT INTO housekeeping (room_id, status, updated_at) 
                                VALUES (:rid, :hk, :now)
                                ON DUPLICATE KEY UPDATE status=:hk, updated_at=:now
                                """,
                                {
                                    "rid": room["room_id"],
                                    "hk": new_hk,
                                    "now": datetime.now(),
                                },
                            )
                            st.success(
                                f"Đã cập nhật phòng {room['room_number']}"
                            )
                            st.rerun()

    st.divider()

    # 5. BẢNG CHI TIẾT DANH SÁCH PHÒNG
    with st.expander("📄 Xem bảng chi tiết danh sách tất cả các phòng"):
        st.dataframe(
            df_rooms[
                [
                    "room_number",
                    "room_type",
                    "floor",
                    "price",
                    "room_status",
                    "hk_status",
                    "hk_staff",
                    "guest_name",
                ]
            ].rename(
                columns={
                    "room_number": "Số phòng",
                    "room_type": "Hạng phòng",
                    "floor": "Tầng",
                    "price": "Giá (VNĐ)",
                    "room_status": "Trạng thái phòng",
                    "hk_status": "Vệ sinh",
                    "hk_staff": "NV Dọn dẹp",
                    "guest_name": "Khách đang ở / đặt",
                }
            ),
            use_container_width=True,
            hide_index=True,
        )


# =========================================================
# CHẠY ĐỘC LẬP HOẶC NHẬP VÀO APP
# =========================================================
if __name__ == "__main__":
    st.set_page_config(
        page_title="Theo dõi tình hình phòng", page_icon="🛏️", layout="wide"
    )
    render_room_tracker_page()
