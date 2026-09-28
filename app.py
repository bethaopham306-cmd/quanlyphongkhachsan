
import sqlite3
from datetime import datetime, date
from pathlib import Path
st.image("IMG_0139.jpeg")
import pandas as pd
import streamlit as st

DB_PATH = Path("hotel.db")

st.set_page_config(
    page_title="Hotel Room Manager",
    page_icon="🏨",
    layout="wide",
    initial_sidebar_state="expanded",
)

ROOM_STATUSES = ["Trống", "Đang ở", "Đã đặt", "Bảo trì", "Dọn phòng"]
ROOM_TYPES = ["Standard", "Deluxe", "Suite", "Family", "VIP"]


# =========================
# DATABASE
# =========================
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS rooms (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            room_number TEXT UNIQUE NOT NULL,
            room_type TEXT NOT NULL,
            floor INTEGER NOT NULL,
            price REAL NOT NULL DEFAULT 0,
            status TEXT NOT NULL DEFAULT 'Trống',
            note TEXT DEFAULT ''
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_code TEXT UNIQUE NOT NULL,
            guest_name TEXT NOT NULL,
            phone TEXT DEFAULT '',
            room_id INTEGER NOT NULL,
            check_in TEXT NOT NULL,
            check_out TEXT NOT NULL,
            guests INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'Đã đặt',
            total REAL NOT NULL DEFAULT 0,
            note TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (room_id) REFERENCES rooms(id)
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            booking_id INTEGER,
            room_id INTEGER,
            transaction_type TEXT NOT NULL,
            amount REAL NOT NULL DEFAULT 0,
            description TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            FOREIGN KEY (booking_id) REFERENCES bookings(id),
            FOREIGN KEY (room_id) REFERENCES rooms(id)
        )
    """)

    conn.commit()

    # Seed dữ liệu mẫu nếu chưa có phòng.
    count = cur.execute("SELECT COUNT(*) FROM rooms").fetchone()[0]
    if count == 0:
        sample_rooms = [
            ("101", "Standard", 1, 650000, "Trống", ""),
            ("102", "Standard", 1, 650000, "Trống", ""),
            ("103", "Deluxe", 1, 900000, "Đang ở", "Khách yêu cầu thêm nước"),
            ("201", "Deluxe", 2, 900000, "Đã đặt", ""),
            ("202", "Suite", 2, 1500000, "Trống", ""),
            ("203", "Suite", 2, 1500000, "Bảo trì", "Đang sửa điều hòa"),
            ("301", "Family", 3, 1800000, "Dọn phòng", ""),
            ("302", "VIP", 3, 3000000, "Trống", ""),
        ]
        cur.executemany("""
            INSERT INTO rooms
            (room_number, room_type, floor, price, status, note)
            VALUES (?, ?, ?, ?, ?, ?)
        """, sample_rooms)
        conn.commit()

    conn.close()


def query_df(sql, params=()):
    conn = get_conn()
    df = pd.read_sql_query(sql, conn, params=params)
    conn.close()
    return df


def execute(sql, params=()):
    conn = get_conn()
    cur = conn.cursor()
    cur.execute(sql, params)
    conn.commit()
    last_id = cur.lastrowid
    conn.close()
    return last_id


def format_vnd(value):
    return f"{float(value):,.0f} đ".replace(",", ".")


def booking_code():
    return "BK" + datetime.now().strftime("%Y%m%d%H%M%S")


# =========================
# HELPERS
# =========================
def sync_room_statuses():
    """Tự động đổi trạng thái phòng dựa trên booking đang hiệu lực."""
    today = date.today().isoformat()
    conn = get_conn()
    cur = conn.cursor()

    # Các booking đã checkout -> không còn chiếm phòng.
    cur.execute("""
        UPDATE bookings
        SET status = 'Đã hoàn tất'
        WHERE check_out < ?
          AND status IN ('Đã đặt', 'Đang ở')
    """, (today,))

    # Phòng có booking đang ở.
    cur.execute("""
        UPDATE rooms
        SET status = 'Đang ở'
        WHERE id IN (
            SELECT room_id
            FROM bookings
            WHERE check_in <= ?
              AND check_out > ?
              AND status IN ('Đã đặt', 'Đang ở')
        )
        AND status NOT IN ('Bảo trì', 'Dọn phòng')
    """, (today, today))

    # Phòng có booking tương lai.
    cur.execute("""
        UPDATE rooms
        SET status = 'Đã đặt'
        WHERE id IN (
            SELECT room_id
            FROM bookings
            WHERE check_in > ?
              AND status = 'Đã đặt'
        )
        AND status NOT IN ('Bảo trì', 'Dọn phòng')
    """, (today,))

    conn.commit()
    conn.close()


def room_is_available(room_id, check_in, check_out, exclude_booking_id=None):
    sql = """
        SELECT COUNT(*) AS c
        FROM bookings
        WHERE room_id = ?
          AND status IN ('Đã đặt', 'Đang ở')
          AND date(check_in) < date(?)
          AND date(check_out) > date(?)
    """
    params = [room_id, check_out, check_in]

    if exclude_booking_id:
        sql += " AND id != ?"
        params.append(exclude_booking_id)

    df = query_df(sql, params)
    return int(df.iloc[0]["c"]) == 0


def calculate_total(room_price, check_in, check_out):
    nights = (check_out - check_in).days
    return nights * float(room_price), nights


# =========================
# INIT
# =========================
init_db()
sync_room_statuses()

# =========================
# SIDEBAR
# =========================
st.sidebar.title("🏨 Hotel Manager")
st.sidebar.caption("Quản lý phòng khách sạn bằng Streamlit + SQLite")

page = st.sidebar.radio(
    "Chức năng",
    [
        "📊 Tổng quan",
        "🛏️ Quản lý phòng",
        "📅 Đặt phòng",
        "👥 Khách lưu trú",
        "💰 Doanh thu",
    ],
)

st.sidebar.divider()
st.sidebar.info(
    "Dữ liệu được lưu cục bộ trong file **hotel.db**. "
    "Bạn có thể chạy ứng dụng ngay trên máy bằng Streamlit."
)


# =========================
# DASHBOARD
# =========================
if page == "📊 Tổng quan":
    st.title("📊 Tổng quan khách sạn")
    st.caption(f"Ngày hiện tại: {date.today().strftime('%d/%m/%Y')}")

    rooms = query_df("SELECT * FROM rooms")
    bookings = query_df("""
        SELECT b.*, r.room_number, r.room_type
        FROM bookings b
        JOIN rooms r ON b.room_id = r.id
        ORDER BY b.check_in ASC
    """)

    total_rooms = len(rooms)
    available = int((rooms["status"] == "Trống").sum()) if total_rooms else 0
    occupied = int((rooms["status"] == "Đang ở").sum()) if total_rooms else 0
    reserved = int((rooms["status"] == "Đã đặt").sum()) if total_rooms else 0
    maintenance = int((rooms["status"].isin(["Bảo trì", "Dọn phòng"])).sum()) if total_rooms else 0

    today_str = date.today().isoformat()
    today_checkins = int((bookings["check_in"] == today_str).sum()) if not bookings.empty else 0
    today_checkouts = int((bookings["check_out"] == today_str).sum()) if not bookings.empty else 0

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Tổng phòng", total_rooms)
    c2.metric("Phòng trống", available)
    c3.metric("Đang ở", occupied)
    c4.metric("Đã đặt", reserved)
    c5.metric("Bảo trì/Dọn", maintenance)

    st.divider()

    c1, c2, c3 = st.columns(3)
    c1.metric("Check-in hôm nay", today_checkins)
    c2.metric("Check-out hôm nay", today_checkouts)

    revenue_df = query_df("""
        SELECT COALESCE(SUM(amount), 0) AS revenue
        FROM transactions
        WHERE transaction_type = 'Thu'
    """)
    revenue = float(revenue_df.iloc[0]["revenue"]) if not revenue_df.empty else 0
    c3.metric("Doanh thu đã thu", format_vnd(revenue))

    st.subheader("🛏️ Tình trạng phòng")

    if rooms.empty:
        st.warning("Chưa có phòng.")
    else:
        status_filter = st.multiselect(
            "Lọc trạng thái",
            ROOM_STATUSES,
            default=ROOM_STATUSES,
        )
        view = rooms[rooms["status"].isin(status_filter)].copy()
        view["Giá/đêm"] = view["price"].apply(format_vnd)
        view = view.rename(columns={
            "room_number": "Số phòng",
            "room_type": "Loại phòng",
            "floor": "Tầng",
            "status": "Trạng thái",
            "note": "Ghi chú",
        })
        st.dataframe(
            view[["Số phòng", "Loại phòng", "Tầng", "Giá/đêm", "Trạng thái", "Ghi chú"]],
            use_container_width=True,
            hide_index=True,
        )

    st.subheader("📅 Lịch đặt phòng gần nhất")
    upcoming = bookings[
        (bookings["status"].isin(["Đã đặt", "Đang ở"]))
        & (bookings["check_out"] >= today_str)
    ].head(10).copy()

    if upcoming.empty:
        st.info("Chưa có booking sắp tới.")
    else:
        upcoming["Tổng tiền"] = upcoming["total"].apply(format_vnd)
        upcoming = upcoming.rename(columns={
            "booking_code": "Mã booking",
            "guest_name": "Khách hàng",
            "room_number": "Phòng",
            "check_in": "Check-in",
            "check_out": "Check-out",
            "status": "Trạng thái",
            "total": "Tổng tiền",
        })
        st.dataframe(
            upcoming[[
                "Mã booking", "Khách hàng", "Phòng",
                "Check-in", "Check-out", "Trạng thái", "Tổng tiền"
            ]],
            use_container_width=True,
            hide_index=True,
        )


# =========================
# ROOM MANAGEMENT
# =========================
elif page == "🛏️ Quản lý phòng":
    st.title("🛏️ Quản lý phòng")

    tab1, tab2, tab3 = st.tabs(["Danh sách phòng", "Thêm phòng", "Chỉnh sửa phòng"])

    with tab1:
        rooms = query_df("SELECT * FROM rooms ORDER BY floor, room_number")
        if rooms.empty:
            st.info("Chưa có phòng.")
        else:
            col1, col2 = st.columns(2)
            with col1:
                floor_options = ["Tất cả"] + sorted(rooms["floor"].unique().tolist())
                selected_floor = st.selectbox("Tầng", floor_options)
            with col2:
                selected_status = st.selectbox("Trạng thái", ["Tất cả"] + ROOM_STATUSES)

            filtered = rooms.copy()
            if selected_floor != "Tất cả":
                filtered = filtered[filtered["floor"] == selected_floor]
            if selected_status != "Tất cả":
                filtered = filtered[filtered["status"] == selected_status]

            filtered["price_display"] = filtered["price"].apply(format_vnd)
            filtered = filtered.rename(columns={
                "room_number": "Số phòng",
                "room_type": "Loại phòng",
                "floor": "Tầng",
                "price_display": "Giá/đêm",
                "status": "Trạng thái",
                "note": "Ghi chú",
            })
            st.dataframe(
                filtered[[
                    "Số phòng", "Loại phòng", "Tầng",
                    "Giá/đêm", "Trạng thái", "Ghi chú"
                ]],
                use_container_width=True,
                hide_index=True,
            )

            st.divider()
            st.subheader("Xóa phòng")

            room_map = {
                f"{r['room_number']} - {r['room_type']}": int(r["id"])
                for _, r in rooms.iterrows()
            }
            selected_room = st.selectbox("Chọn phòng cần xóa", list(room_map.keys()))
            if st.button("🗑️ Xóa phòng", type="secondary"):
                room_id = room_map[selected_room]
                booking_count = query_df(
                    "SELECT COUNT(*) AS c FROM bookings WHERE room_id = ?",
                    [room_id],
                ).iloc[0]["c"]

                if int(booking_count) > 0:
                    st.error("Không thể xóa phòng đã có lịch sử đặt phòng.")
                else:
                    execute("DELETE FROM rooms WHERE id = ?", [room_id])
                    st.success("Đã xóa phòng.")
                    st.rerun()

    with tab2:
        with st.form("add_room_form"):
            c1, c2 = st.columns(2)
            with c1:
                room_number = st.text_input("Số phòng *", placeholder="Ví dụ: 401")
                room_type = st.selectbox("Loại phòng *", ROOM_TYPES)
                floor = st.number_input("Tầng *", min_value=1, max_value=100, value=1)
            with c2:
                price = st.number_input(
                    "Giá phòng/đêm (VNĐ) *",
                    min_value=0,
                    value=650000,
                    step=50000,
                )
                status = st.selectbox("Trạng thái", ROOM_STATUSES)
                note = st.text_area("Ghi chú")

            submitted = st.form_submit_button("➕ Thêm phòng", type="primary")

        if submitted:
            if not room_number.strip():
                st.error("Vui lòng nhập số phòng.")
            else:
                try:
                    execute("""
                        INSERT INTO rooms
                        (room_number, room_type, floor, price, status, note)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, [
                        room_number.strip(),
                        room_type,
                        int(floor),
                        float(price),
                        status,
                        note.strip(),
                    ])
                    st.success(f"Đã thêm phòng {room_number}.")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Số phòng này đã tồn tại.")

    with tab3:
        rooms = query_df("SELECT * FROM rooms ORDER BY room_number")
        if rooms.empty:
            st.info("Chưa có phòng để chỉnh sửa.")
        else:
            room_map = {
                f"{r['room_number']} - {r['room_type']}": int(r["id"])
                for _, r in rooms.iterrows()
            }
            selected_label = st.selectbox("Chọn phòng", list(room_map.keys()))
            room_id = room_map[selected_label]
            room = rooms[rooms["id"] == room_id].iloc[0]

            with st.form("edit_room_form"):
                c1, c2 = st.columns(2)
                with c1:
                    new_number = st.text_input(
                        "Số phòng",
                        value=str(room["room_number"]),
                    )
                    new_type = st.selectbox(
                        "Loại phòng",
                        ROOM_TYPES,
                        index=ROOM_TYPES.index(room["room_type"])
                        if room["room_type"] in ROOM_TYPES else 0,
                    )
                    new_floor = st.number_input(
                        "Tầng",
                        min_value=1,
                        max_value=100,
                        value=int(room["floor"]),
                    )
                with c2:
                    new_price = st.number_input(
                        "Giá phòng/đêm (VNĐ)",
                        min_value=0,
                        value=float(room["price"]),
                        step=50000.0,
                    )
                    new_status = st.selectbox(
                        "Trạng thái",
                        ROOM_STATUSES,
                        index=ROOM_STATUSES.index(room["status"])
                        if room["status"] in ROOM_STATUSES else 0,
                    )
                    new_note = st.text_area(
                        "Ghi chú",
                        value=str(room["note"] or ""),
                    )

                submitted = st.form_submit_button("💾 Lưu thay đổi", type="primary")

            if submitted:
                try:
                    execute("""
                        UPDATE rooms
                        SET room_number = ?, room_type = ?, floor = ?,
                            price = ?, status = ?, note = ?
                        WHERE id = ?
                    """, [
                        new_number.strip(),
                        new_type,
                        int(new_floor),
                        float(new_price),
                        new_status,
                        new_note.strip(),
                        room_id,
                    ])
                    st.success("Đã cập nhật phòng.")
                    st.rerun()
                except sqlite3.IntegrityError:
                    st.error("Số phòng mới đã tồn tại.")


# =========================
# BOOKING
# =========================
elif page == "📅 Đặt phòng":
    st.title("📅 Quản lý đặt phòng")

    tab1, tab2 = st.tabs(["Tạo booking", "Danh sách booking"])

    with tab1:
        rooms = query_df("""
            SELECT * FROM rooms
            WHERE status != 'Bảo trì'
            ORDER BY floor, room_number
        """)

        if rooms.empty:
            st.warning("Chưa có phòng phù hợp để đặt.")
        else:
            with st.form("booking_form"):
                c1, c2 = st.columns(2)

                with c1:
                    guest_name = st.text_input("Tên khách *")
                    phone = st.text_input("Số điện thoại")
                    guests = st.number_input(
                        "Số lượng khách",
                        min_value=1,
                        max_value=20,
                        value=1,
                    )
                    room_labels = {
                        f"Phòng {r['room_number']} | {r['room_type']} | {format_vnd(r['price'])}/đêm":
                        int(r["id"])
                        for _, r in rooms.iterrows()
                    }
                    selected_room_label = st.selectbox(
                        "Phòng *",
                        list(room_labels.keys()),
                    )

                with c2:
                    check_in = st.date_input(
                        "Ngày check-in *",
                        value=date.today(),
                        min_value=date.today(),
                    )
                    check_out = st.date_input(
                        "Ngày check-out *",
                        value=date.today(),
                        min_value=date.today(),
                    )
                    booking_status = st.selectbox(
                        "Trạng thái booking",
                        ["Đã đặt", "Đang ở"],
                    )
                    note = st.text_area("Ghi chú")

                submitted = st.form_submit_button(
                    "📌 Tạo booking",
                    type="primary",
                )

            if submitted:
                if not guest_name.strip():
                    st.error("Vui lòng nhập tên khách.")
                elif check_out <= check_in:
                    st.error("Ngày check-out phải sau ngày check-in.")
                else:
                    room_id = room_labels[selected_room_label]
                    room_price = float(
                        rooms[rooms["id"] == room_id].iloc[0]["price"]
                    )

                    available = room_is_available(
                        room_id,
                        check_in.isoformat(),
                        check_out.isoformat(),
                    )

                    if not available:
                        st.error("Phòng đã có booking trùng thời gian.")
                    else:
                        total, nights = calculate_total(
                            room_price, check_in, check_out
                        )
                        code = booking_code()

                        execute("""
                            INSERT INTO bookings
                            (booking_code, guest_name, phone, room_id,
                             check_in, check_out, guests, status,
                             total, note, created_at)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, [
                            code,
                            guest_name.strip(),
                            phone.strip(),
                            room_id,
                            check_in.isoformat(),
                            check_out.isoformat(),
                            int(guests),
                            booking_status,
                            total,
                            note.strip(),
                            datetime.now().isoformat(timespec="seconds"),
                        ])

                        execute("""
                            INSERT INTO transactions
                            (booking_id, room_id, transaction_type,
                             amount, description, created_at)
                            VALUES (
                                (SELECT id FROM bookings WHERE booking_code = ?),
                                ?, 'Thu', ?, ?, ?
                            )
                        """, [
                            code,
                            room_id,
                            total,
                            f"Tiền phòng booking {code}",
                            datetime.now().isoformat(timespec="seconds"),
                        ])

                        # Chỉ cập nhật trạng thái nếu không phải bảo trì/dọn phòng.
                        execute("""
                            UPDATE rooms
                            SET status = ?
                            WHERE id = ?
                              AND status NOT IN ('Bảo trì', 'Dọn phòng')
                        """, [
                            "Đang ở" if booking_status == "Đang ở" else "Đã đặt",
                            room_id,
                        ])

                        st.success(
                            f"Đã tạo booking **{code}** - "
                            f"{nights} đêm - Tổng tiền: **{format_vnd(total)}**"
                        )
                        st.rerun()

    with tab2:
        bookings = query_df("""
            SELECT
                b.id, b.booking_code, b.guest_name, b.phone,
                r.room_number, r.room_type,
                b.check_in, b.check_out, b.guests,
                b.status, b.total, b.note, b.created_at
            FROM bookings b
            JOIN rooms r ON b.room_id = r.id
            ORDER BY b.check_in DESC, b.id DESC
        """)

        if bookings.empty:
            st.info("Chưa có booking.")
        else:
            status_filter = st.selectbox(
                "Lọc booking",
                ["Tất cả", "Đã đặt", "Đang ở", "Đã hoàn tất", "Đã hủy"],
            )
            view = bookings.copy()
            if status_filter != "Tất cả":
                view = view[view["status"] == status_filter]

            view["total_display"] = view["total"].apply(format_vnd)
            view = view.rename(columns={
                "booking_code": "Mã booking",
                "guest_name": "Khách",
                "phone": "Điện thoại",
                "room_number": "Phòng",
                "room_type": "Loại",
                "check_in": "Check-in",
                "check_out": "Check-out",
                "guests": "Số khách",
                "status": "Trạng thái",
                "total_display": "Tổng tiền",
                "note": "Ghi chú",
            })

            st.dataframe(
                view[[
                    "Mã booking", "Khách", "Điện thoại", "Phòng",
                    "Loại", "Check-in", "Check-out",
                    "Số khách", "Trạng thái", "Tổng tiền", "Ghi chú"
                ]],
                use_container_width=True,
                hide_index=True,
            )

            st.divider()
            st.subheader("Cập nhật trạng thái booking")

            active = bookings[
                bookings["status"].isin(["Đã đặt", "Đang ở"])
            ]

            if active.empty:
                st.info("Không có booking đang hoạt động.")
            else:
                booking_map = {
                    f"{r['booking_code']} - {r['guest_name']} - Phòng {r['room_number']}":
                    int(r["id"])
                    for _, r in active.iterrows()
                }
                selected = st.selectbox(
                    "Chọn booking",
                    list(booking_map.keys()),
                )
                new_status = st.selectbox(
                    "Trạng thái mới",
                    ["Đã đặt", "Đang ở", "Đã hoàn tất", "Đã hủy"],
                )

                if st.button("💾 Cập nhật booking", type="primary"):
                    booking_id = booking_map[selected]

                    booking_row = bookings[
                        bookings["id"] == booking_id
                    ].iloc[0]
                    room_id = int(
                        query_df(
                            "SELECT room_id FROM bookings WHERE id = ?",
                            [booking_id],
                        ).iloc[0]["room_id"]
                    )

                    execute(
                        "UPDATE bookings SET status = ? WHERE id = ?",
                        [new_status, booking_id],
                    )

                    if new_status in ["Đã hoàn tất", "Đã hủy"]:
                        execute("""
                            UPDATE rooms
                            SET status = 'Trống'
                            WHERE id = ?
                              AND status NOT IN ('Bảo trì', 'Dọn phòng')
                        """, [room_id])
                    elif new_status == "Đang ở":
                        execute("""
                            UPDATE rooms SET status = 'Đang ở'
                            WHERE id = ?
                              AND status NOT IN ('Bảo trì', 'Dọn phòng')
                        """, [room_id])
                    elif new_status == "Đã đặt":
                        execute("""
                            UPDATE rooms SET status = 'Đã đặt'
                            WHERE id = ?
                              AND status NOT IN ('Bảo trì', 'Dọn phòng')
                        """, [room_id])

                    st.success("Đã cập nhật trạng thái.")
                    st.rerun()


# =========================
# GUESTS
# =========================
elif page == "👥 Khách lưu trú":
    st.title("👥 Khách lưu trú")

    search = st.text_input(
        "🔎 Tìm theo tên khách, số điện thoại hoặc mã booking",
        placeholder="Nhập từ khóa...",
    )

    sql = """
        SELECT
            b.booking_code,
            b.guest_name,
            b.phone,
            r.room_number,
            r.room_type,
            b.check_in,
            b.check_out,
            b.guests,
            b.status,
            b.total,
            b.note
        FROM bookings b
        JOIN rooms r ON b.room_id = r.id
        WHERE 1=1
    """
    params = []

    if search.strip():
        sql += """
            AND (
                b.guest_name LIKE ?
                OR b.phone LIKE ?
                OR b.booking_code LIKE ?
            )
        """
        keyword = f"%{search.strip()}%"
        params.extend([keyword, keyword, keyword])

    sql += " ORDER BY b.check_in DESC"

    guests = query_df(sql, params)

    if guests.empty:
        st.info("Không tìm thấy khách.")
    else:
        guests["total_display"] = guests["total"].apply(format_vnd)
        guests = guests.rename(columns={
            "booking_code": "Mã booking",
            "guest_name": "Tên khách",
            "phone": "Điện thoại",
            "room_number": "Phòng",
            "room_type": "Loại phòng",
            "check_in": "Check-in",
            "check_out": "Check-out",
            "guests": "Số khách",
            "status": "Trạng thái",
            "total_display": "Tổng tiền",
            "note": "Ghi chú",
        })

        st.dataframe(
            guests[[
                "Mã booking", "Tên khách", "Điện thoại", "Phòng",
                "Loại phòng", "Check-in", "Check-out",
                "Số khách", "Trạng thái", "Tổng tiền", "Ghi chú"
            ]],
            use_container_width=True,
            hide_index=True,
        )

        st.download_button(
            "⬇️ Xuất danh sách CSV",
            data=guests.to_csv(index=False).encode("utf-8-sig"),
            file_name="danh_sach_khach.csv",
            mime="text/csv",
        )


# =========================
# REVENUE
# =========================
elif page == "💰 Doanh thu":
    st.title("💰 Doanh thu")

    transactions = query_df("""
        SELECT
            t.id,
            t.created_at,
            t.transaction_type,
            t.amount,
            t.description,
            r.room_number,
            b.booking_code,
            b.guest_name
        FROM transactions t
        LEFT JOIN rooms r ON t.room_id = r.id
        LEFT JOIN bookings b ON t.booking_id = b.id
        ORDER BY t.created_at DESC
    """)

    total_revenue = (
        float(transactions.loc[
            transactions["transaction_type"] == "Thu", "amount"
        ].sum())
        if not transactions.empty else 0
    )

    total_expense = (
        float(transactions.loc[
            transactions["transaction_type"] == "Chi", "amount"
        ].sum())
        if not transactions.empty else 0
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("Tổng thu", format_vnd(total_revenue))
    c2.metric("Tổng chi", format_vnd(total_expense))
    c3.metric("Lợi nhuận tạm tính", format_vnd(total_revenue - total_expense))

    st.divider()

    if transactions.empty:
        st.info("Chưa có giao dịch.")
    else:
        display = transactions.copy()
        display["amount_display"] = display["amount"].apply(format_vnd)
        display = display.rename(columns={
            "created_at": "Thời gian",
            "transaction_type": "Loại",
            "amount_display": "Số tiền",
            "description": "Nội dung",
            "room_number": "Phòng",
            "booking_code": "Booking",
            "guest_name": "Khách",
        })

        st.dataframe(
            display[[
                "Thời gian", "Loại", "Số tiền",
                "Nội dung", "Phòng", "Booking", "Khách"
            ]],
            use_container_width=True,
            hide_index=True,
        )

    st.subheader("➕ Thêm giao dịch")
    rooms = query_df("SELECT * FROM rooms ORDER BY room_number")
    bookings = query_df("""
        SELECT b.id, b.booking_code, b.guest_name, r.room_number
        FROM bookings b
        JOIN rooms r ON b.room_id = r.id
        ORDER BY b.id DESC
    """)

    with st.form("transaction_form"):
        c1, c2 = st.columns(2)
        with c1:
            trans_type = st.selectbox("Loại giao dịch", ["Thu", "Chi"])
            amount = st.number_input(
                "Số tiền (VNĐ)",
                min_value=0.0,
                value=0.0,
                step=50000.0,
            )
            description = st.text_input("Nội dung")

        with c2:
            if rooms.empty:
                room_id = None
                st.info("Chưa có phòng.")
            else:
                room_map = {
                    f"Phòng {r['room_number']}": int(r["id"])
                    for _, r in rooms.iterrows()
                }
                room_label = st.selectbox(
                    "Phòng liên quan",
                    ["Không chọn"] + list(room_map.keys()),
                )
                room_id = None if room_label == "Không chọn" else room_map[room_label]

            if bookings.empty:
                booking_id = None
            else:
                booking_map = {
                    f"{r['booking_code']} - {r['guest_name']} - Phòng {r['room_number']}":
                    int(r["id"])
                    for _, r in bookings.iterrows()
                }
                booking_label = st.selectbox(
                    "Booking liên quan",
                    ["Không chọn"] + list(booking_map.keys()),
                )
                booking_id = None if booking_label == "Không chọn" else booking_map[booking_label]

        submitted = st.form_submit_button("➕ Lưu giao dịch", type="primary")

    if submitted:
        if amount <= 0:
            st.error("Số tiền phải lớn hơn 0.")
        else:
            execute("""
                INSERT INTO transactions
                (booking_id, room_id, transaction_type, amount,
                 description, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
            """, [
                booking_id,
                room_id,
                trans_type,
                float(amount),
                description.strip(),
                datetime.now().isoformat(timespec="seconds"),
            ])
            st.success("Đã lưu giao dịch.")
            st.rerun()


st.sidebar.divider()
st.sidebar.caption("© Hotel Room Manager • Streamlit")
