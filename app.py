import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import datetime
import uuid

# --- 1. CẤU HÌNH & DANH MỤC (GIỮ NGUYÊN) ---
st.set_page_config(page_title="Hệ thống QLVT PC Tây Ninh - v42 Full Fixed", layout="wide")
DANM_MUC_NCC = {
    "Công tơ": ["Vinasino", "Gelex", "Hữu Hồng", "OMNI", "Psmart", "Landis+Gyr"],
    "DCU": ["Vinasino", "Hữu Hồng", "OMNI", "Psmart", "Gelex"],
    "Sim": ["Viettel", "Vina", "Mobi", "Sim đấu thầu"],
    "Module": ["Module RS485", "Module PLC"],
    "Modem": ["Nam Thanh", "Gelex", "Hữu Hồng", "IFC", "Senvi"]
}
CO_SO = ["PC Tây Ninh - Cơ sở 1", "PC Tây Ninh - Cơ sở 2"]
NGUON_NHAP_NGOAI = ["EVNSPC", "PC Đồng Nai", "PC Bình Dương", "PC Bà Rịa - Vũng Tàu", "PC Long An", "PC Tiền Giang", "Mua sắm tập trung", "Khác"]
DANH_SACH_14_DOI = [f"PB06{str(i).zfill(2)} {name}" for i, name in enumerate(["Tân An", "Thủ Thừa", "Đức Hòa", "Cần Giuộc", "Kiến Tường", "Bến Lức", "Cần Đước", "Tân Thạnh", "Tân Trụ", "Đức Huệ", "Thạnh Hóa", "Vĩnh Hưng", "Tân Hưng", "Tầm Vu"], 1)]
TRANG_THAI_LIST = ["Dưới kho", "Đã đưa lên lưới"]
MUC_DICH_LIST = ["Lắp TCD", "Lắp TCC", "Lắp KH sau TCC", "Dự phòng tại kho"]
USER_DB = {"admin": "123", **{doi: "123" for doi in DANH_SACH_14_DOI}}

# --- 2. KẾT NỐI DỮ LIỆU ---
def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        inv = conn.read(worksheet="inventory", ttl=0).dropna(how="all").astype(str)
        req = conn.read(worksheet="requests", ttl=0).dropna(how="all").astype(str)
        return inv, req
    except Exception:
        inv_cols = ['ID_He_Thong', 'Loại_VT', 'Mã_TB', 'Số_Seri', 'Nhà_CC', 'Nguồn_Nhap', 'Vị_Trí_Kho', 'Trạng_Thái_Luoi', 'Mục_Đích', 'Vị_Tiết_Chi_Tiết', 'Thoi_Gian_Tao', 'Thoi_Gian_Cap_Phat']
        req_cols = ['Thời_Gian_Báo', 'Đơn_Vị', 'Loại_VT', 'Tên_Vật_Tư', 'Nhà_CC', 'Số_Lượng', 'Lý_Do', 'Trạng_Thái', 'Thời_Gian_Bù']
        return pd.DataFrame(columns=inv_cols), pd.DataFrame(columns=req_cols)

if 'inventory' not in st.session_state:
    st.session_state.inventory, st.session_state.requests = load_data()

def sync():
    conn = st.connection("gsheets", type=GSheetsConnection)
    with st.spinner("🔄 Đang đồng bộ Cloud..."):
        conn.update(worksheet="inventory", data=st.session_state.inventory, validate=False)
        conn.update(worksheet="requests", data=st.session_state.requests, validate=False)

# --- 3. DIALOG XÁC NHẬN ---
@st.dialog("XÁC NHẬN")
def confirm(action, data=None):
    st.warning("⚠️ Dữ liệu sẽ ghi vào Google Sheets.")
    if st.button("✅ XÁC NHẬN", use_container_width=True):
        now_s = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        if action == "nhap":
            st.session_state.inventory = pd.concat([st.session_state.inventory, data], ignore_index=True)
        elif action == "cap":
            for _, r in data.iterrows():
                mask = (st.session_state.inventory['Vị_Trí_Kho'] == str(r['Từ_Kho'])) & (st.session_state.inventory['Mã_TB'] == str(r['Mã_TB']))
                idx = st.session_state.inventory[mask].head(int(r['Số_Lượng'])).index
                st.session_state.inventory.loc[idx, 'Vị_Trí_Kho'] = str(r['Đến_Đơn_Vị'])
                st.session_state.inventory.loc[idx, 'Thoi_Gian_Cap_Phat'] = now_s
        elif action == "hien_truong":
            for _, row in data.iterrows():
                st.session_state.inventory.loc[st.session_state.inventory['ID_He_Thong'] == str(row['ID_He_Thong']), ['Số_Seri', 'Trạng_Thái_Luoi', 'Mục_Đích', 'Vị_Tiết_Chi_Tiết']] = row[['Số_Seri', 'Trạng_Thái_Luoi', 'Mục_Đích', 'Vị_Tiết_Chi_Tiết']].values
        elif action == "xoa":
            st.session_state.inventory = st.session_state.inventory[~st.session_state.inventory['ID_He_Thong'].isin(data)]
        sync(); st.rerun()

# --- 4. ĐĂNG NHẬP ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if not st.session_state.logged_in:
    u = st.selectbox("Tài khoản", ["admin"] + DANH_SACH_14_DOI)
    p = st.text_input("Mật khẩu", type="password")
    if st.button("🔓 Đăng nhập"):
        if p == USER_DB.get(u):
            st.session_state.logged_in, st.session_state.user_role, st.session_state.user_name = True, ("admin" if u=="admin" else "doi"), u
            st.rerun()
    st.stop()

# --- 5. MENU SIDEBAR ---
menu = st.sidebar.radio("MENU", ["📊 Dashboard", "📥 Nhập & Excel", "🚚 Cấp phát & Excel", "🚨 Duyệt hỏng"]) if st.session_state.user_role == "admin" else st.sidebar.radio("MENU", ["🛠️ Hiện trường", "🚨 Báo hỏng"])

# --- 6. CHI TIẾT CHỨC NĂNG ---
if menu == "📊 Dashboard":
    st.header("Tổng quan vật tư")
    df = st.session_state.inventory.copy()
    if not df.empty:
        c1, c2 = st.columns(2)
        with c1: st.plotly_chart(px.pie(df, names='Trạng_Thái_Luoi', title="Trạng thái"), use_container_width=True)
        with c2: st.plotly_chart(px.bar(df.groupby(['Vị_Trí_Kho']).size().reset_index(name='SL'), x='Vị_Trí_Kho', y='SL', title="Vật tư theo kho"), use_container_width=True)
        df.insert(0, "Xóa", False)
        ed = st.data_editor(df, use_container_width=True, hide_index=True)
        to_del = ed[ed["Xóa"] == True]["ID_He_Thong"].tolist()
        if to_del and st.button("🗑️ Xóa dòng chọn"): confirm("xoa", to_del)

elif menu == "📥 Nhập & Excel":
    st.header("Tiếp nhận vật tư")
    t1, t2 = st.tabs(["✍️ Nhập tay", "📁 Excel Nhập"])
    with t1:
        # LỖI FIX Ở ĐÂY: Tách lvt ra ngoài form để NCC tự động cập nhật
        lvt = st.selectbox("1. Loại vật tư", list(DANM_MUC_NCC.keys()), key="lvt_nhap")
        with st.form("f_nhap_tay"):
            ncc = st.selectbox("2. Nhà cung cấp", DANM_MUC_NCC[lvt])
            c1, c2 = st.columns(2)
            with c1: ng, kh = st.selectbox("Nguồn", NGUON_NHAP_NGOAI), st.selectbox("Kho", CO_SO)
            with c2: mod, sl = st.text_input("Model"), st.number_input("Số lượng", min_value=1, step=1)
            if st.form_submit_button("🚀 Xác nhận Nhập"):
                new = pd.DataFrame([{'ID_He_Thong': f"TN-{uuid.uuid4().hex[:8].upper()}", 'Loại_VT': lvt, 'Mã_TB': mod, 'Số_Seri': 'Chưa nhập', 'Nhà_CC': ncc, 'Nguồn_Nhap': ng, 'Vị_Trí_Kho': kh, 'Trạng_Thái_Luoi': 'Dưới kho', 'Thoi_Gian_Tao': datetime.datetime.now().strftime("%d/%m/%Y")} for _ in range(int(sl))])
                confirm("nhap", new)
    with t2:
        st.info("Cột Excel: Loại_VT, Nhà_CC, Mã_TB, Năm_SX, Nguồn_Nhap, Vị_Trí_Kho")
        f = st.file_uploader("Nạp Excel Tiếp nhận", type=["xlsx"])
        if f:
            df_ex = pd.read_excel(f).astype(str)
            st.dataframe(df_ex.head())
            if st.button("📥 Nạp vào Cloud"):
                df_ex['ID_He_Thong'] = [f"TN-{uuid.uuid4().hex[:6].upper()}" for _ in range(len(df_ex))]
                df_ex['Thoi_Gian_Tao'] = datetime.datetime.now().strftime("%d/%m/%Y")
                confirm("nhap", df_ex)

elif menu == "🚚 Cấp phát & Excel":
    st.header("Phân bổ về Đội")
    t1, t2 = st.tabs(["✍️ Cấp phát tay", "📁 Excel Cấp phát"])
    with t1:
        tk, lvt_c = st.selectbox("Từ kho", CO_SO), st.selectbox("Loại VT", list(DANM_MUC_NCC.keys()))
        avai = st.session_state.inventory[(st.session_state.inventory['Vị_Trí_Kho']==tk) & (st.session_state.inventory['Loại_VT']==lvt_c)]
        with st.form("f_c"):
            m_c = st.selectbox("Model", avai['Mã_TB'].unique() if not avai.empty else ["Trống"])
            den, sl_c = st.selectbox("Đến Đội", DANH_SACH_14_DOI), st.number_input("SL", min_value=1)
            if st.form_submit_button("🚀 Cấp"):
                confirm("cap", pd.DataFrame([{'Từ_Kho': tk, 'Đến_Đơn_Vị': den, 'Mã_TB': m_c, 'Số_Lượng': sl_c}]))
    with t2:
        st.info("Cột Excel: Từ_Kho, Đến_Đơn_Vị, Mã_TB, Số_Lượng")
        f2 = st.file_uploader("Nạp Excel Cấp phát", type=["xlsx"])
        if f2:
            df2 = pd.read_excel(f2).astype(str)
            st.dataframe(df2)
            if st.button("🚀 Thực hiện phân bổ"): confirm("cap", df2)

elif menu == "🛠️ Hiện trường":
    st.header(f"Đội: {st.session_state.user_name}")
    df_dv = st.session_state.inventory[st.session_state.inventory['Vị_Trí_Kho'] == st.session_state.user_name]
    if not df_dv.empty:
        ed = st.data_editor(df_dv[['ID_He_Thong', 'Mã_TB', 'Số_Seri', 'Trạng_Thái_Luoi', 'Mục_Đích', 'Vị_Tiết_Chi_Tiết']],
            column_config={"Trạng_Thái_Luoi": st.column_config.SelectboxColumn("TT", options=TRANG_THAI_LIST), "Mục_Đích": st.column_config.SelectboxColumn("Vị trí", options=MUC_DICH_LIST)},
            disabled=['ID_He_Thong', 'Mã_TB'], use_container_width=True, hide_index=True)
        if st.button("💾 Lưu hiện trường"): confirm("hien_truong", ed)

elif menu == "🚨 Báo hỏng":
    st.header("Yêu cầu bù hàng")
    lvt_h = st.selectbox("Loại VT hỏng", list(DANM_MUC_NCC.keys()), key="lvt_h")
    with st.form("f_h"):
        ncc_h = st.selectbox("Nhà CC", DANM_MUC_NCC[lvt_h])
        tvt, sl_h = st.text_input("Tên/Model"), st.number_input("SL", min_value=1)
        if st.form_submit_button("🚨 Gửi báo hỏng"):
            new_h = pd.DataFrame([{'Thời_Gian_Báo': datetime.datetime.now().strftime("%d/%m/%Y"), 'Đơn_Vị': st.session_state.user_name, 'Loại_VT': lvt_h, 'Tên_Vật_Tư': tvt, 'Nhà_CC': ncc_h, 'Số_Lượng': sl_h, 'Trạng_Thái': 'Chờ xử lý'}])
            st.session_state.requests = pd.concat([st.session_state.requests, new_h], ignore_index=True)
            sync(); st.rerun()

elif menu == "🚨 Duyệt hỏng":
    st.data_editor(st.session_state.requests, use_container_width=True)
    if st.button("💾 Lưu Cloud"): sync(); st.rerun()
