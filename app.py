import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import datetime
import io
import uuid

# --- 1. CẤU HÌNH HỆ THỐNG ---
st.set_page_config(page_title="Hệ thống QLVT PC Tây Ninh - v42 Full Option", layout="wide")
NAM_HIEN_TAI = datetime.datetime.now().year

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

# --- 2. KẾT NỐI GOOGLE SHEETS ---
def load_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        inv = conn.read(worksheet="inventory", ttl=0).dropna(how="all").astype(str)
        req = conn.read(worksheet="requests", ttl=0).dropna(how="all").astype(str)
        return inv, req
    except Exception:
        inv_cols = ['ID_He_Thong', 'Năm_SX', 'Loại_VT', 'Mã_TB', 'Số_Seri', 'Nhà_CC', 'Nguồn_Nhap', 'Vị_Trí_Kho', 'Trạng_Thái_Luoi', 'Mục_Đích', 'Vị_Tiết_Chi_Tiết', 'Thoi_Gian_Tao', 'Thoi_Gian_Cap_Phat']
        req_cols = ['Thời_Gian_Báo', 'Đơn_Vị', 'Loại_VT', 'Tên_Vật_Tư', 'Nhà_CC', 'Chủng_Loại', 'Số_Lượng', 'Lý_Do', 'Trạng_Thái', 'Thời_Gian_Bù']
        return pd.DataFrame(columns=inv_cols), pd.DataFrame(columns=req_cols)

if 'inventory' not in st.session_state:
    st.session_state.inventory, st.session_state.requests = load_data()

def sync_to_cloud():
    conn = st.connection("gsheets", type=GSheetsConnection)
    with st.spinner("🔄 Đang đồng bộ dữ liệu lên Cloud..."):
        conn.update(worksheet="inventory", data=st.session_state.inventory)
        conn.update(worksheet="requests", data=st.session_state.requests)

# --- 3. TRUNG TÂM XÁC NHẬN ---
@st.dialog("XÁC NHẬN NGHIỆP VỤ")
def confirm_dialog(action, data=None):
    st.warning("⚠️ Hệ thống yêu cầu xác nhận để ghi dữ liệu lên Google Sheets.")
    if st.button("✅ XÁC NHẬN", use_container_width=True):
        now_s = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        if action == "nhap":
            st.session_state.inventory = pd.concat([st.session_state.inventory, data], ignore_index=True)
        elif action == "cap_phat":
            for _, r in data.iterrows():
                mask = (st.session_state.inventory['Vị_Trí_Kho'] == str(r['Từ_Kho'])) & (st.session_state.inventory['Mã_TB'] == str(r['Mã_TB']))
                idx = st.session_state.inventory[mask].head(int(r['Số_Lượng'])).index
                st.session_state.inventory.loc[idx, 'Vị_Trí_Kho'] = str(r['Đến_Đơn_Vị'])
                st.session_state.inventory.loc[idx, 'Thoi_Gian_Cap_Phat'] = now_s
        elif action == "hien_truong":
            for _, row in data.iterrows():
                st.session_state.inventory.loc[st.session_state.inventory['ID_He_Thong'] == str(row['ID_He_Thong']), 
                ['Số_Seri', 'Trạng_Thái_Luoi', 'Mục_Đích', 'Vị_Tiết_Chi_Tiết']] = row[['Số_Seri', 'Trạng_Thái_Luoi', 'Mục_Đích', 'Vị_Tiết_Chi_Tiết']].values
        elif action == "bao_hong":
            st.session_state.requests = pd.concat([st.session_state.requests, data], ignore_index=True)
        elif action == "duyet_hong":
            st.session_state.requests.loc[data, 'Trạng_Thái'] = "Đã bù hàng"
            st.session_state.requests.loc[data, 'Thời_Gian_Bù'] = now_s
        elif action == "xoa":
            st.session_state.inventory = st.session_state.inventory[~st.session_state.inventory['ID_He_Thong'].isin(data)]
            
        sync_to_cloud()
        st.success("Dữ liệu đã được cập nhật Cloud!"); st.rerun()

# --- 4. ĐĂNG NHẬP ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if not st.session_state.logged_in:
    st.markdown("<h1 style='text-align:center; color:#1E3A8A;'>QLVT PC TÂY NINH</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,1.5,1])
    with c2:
        u = st.selectbox("Tài khoản", ["admin"] + DANH_SACH_14_DOI)
        p = st.text_input("Mật khẩu", type="password")
        if st.button("🔓 Đăng nhập"):
            if p == USER_DB.get(u):
                st.session_state.logged_in, st.session_state.user_role, st.session_state.user_name = True, ("admin" if u=="admin" else "doi"), u
                st.rerun()
            else: st.error("Mật khẩu sai!")
    st.stop()

# --- 5. SIDEBAR ---
st.sidebar.write(f"👤 Tài khoản: **{st.session_state.user_name}**")
if st.sidebar.button("Đăng xuất"): st.session_state.logged_in = False; st.rerun()

if st.session_state.user_role == "admin":
    menu = st.sidebar.radio("CÔNG TY", ["📊 Dashboard", "📥 Nhập Kho", "🚚 Cấp Phát", "🚨 Duyệt Báo Hỏng"])
else:
    menu = st.sidebar.radio("ĐỘI QLĐ", ["🛠️ Hiện trường (Seri)", "🚨 Báo Hỏng"])

# --- 6. CHI TIẾT CHỨC NĂNG ---

# A. DASHBOARD
if menu == "📊 Dashboard":
    st.header("Dashboard Giám Sát Lưới")
    df = st.session_state.inventory.copy()
    if not df.empty:
        c1, c2 = st.columns(2)
        with c1: st.plotly_chart(px.pie(df, names='Trạng_Thái_Luoi', title="Tỷ lệ Trên lưới/Dưới kho"), use_container_width=True)
        with c2: st.plotly_chart(px.bar(df.groupby(['Vị_Trí_Kho', 'Trạng_Thái_Luoi']).size().reset_index(name='SL'), x='Vị_Trí_Kho', y='SL', color='Trạng_Thái_Luoi', title="Vật tư theo từng đơn vị"), use_container_width=True)
        st.markdown("---")
        df.insert(0, "Xóa", False)
        ed = st.data_editor(df, use_container_width=True)
        to_del = ed[ed["Xóa"] == True]["ID_He_Thong"].tolist()
        if to_del and st.button("🗑️ Xóa vĩnh viễn trên Cloud"): confirm_dialog("xoa", to_del)
    else: st.info("Dữ liệu trống.")

# B. NHẬP KHO (SỬA LỖI NHÀ CUNG CẤP TẠI ĐÂY)
elif menu == "📥 Nhập Kho":
    st.header("Nhập Vật Tư Mới")
    t1, t2 = st.tabs(["✍️ Nhập tay", "📁 Excel Nhập"])
    with t1:
        # Tách chọn Loại VT ra ngoài form để Nhà CC cập nhật ngay lập tức
        lvt = st.selectbox("1. Loại vật tư", list(DANM_MUC_NCC.keys()))
        ncc_list = DANM_MUC_NCC[lvt] # Lấy danh sách NCC tương ứng
        
        with st.form("f_nhap_tay"):
            ncc = st.selectbox("2. Nhà cung cấp", ncc_list)
            c1, c2 = st.columns(2)
            with c1: 
                ng = st.selectbox("3. Nguồn nhập", NGUON_NHAP_NGOAI)
                kh = st.selectbox("4. Nhập vào kho", CO_SO)
            with c2: 
                mod = st.text_input("5. Model/Mã thiết bị")
                sl = st.number_input("6. Số lượng", min_value=1)
                
            if st.form_submit_button("🚀 Xác nhận Nhập"):
                now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                new_data = pd.DataFrame([{
                    'ID_He_Thong': f"TN-{uuid.uuid4().hex[:8].upper()}", 'Năm_SX': NAM_HIEN_TAI, 'Loại_VT': lvt, 
                    'Mã_TB': mod, 'Số_Seri': 'Chưa nhập', 'Nhà_CC': ncc, 'Nguồn_Nhap': ng, 'Vị_Trí_Kho': kh, 
                    'Trạng_Thái_Luoi': 'Dưới kho', 'Thoi_Gian_Tao': now
                } for _ in range(int(sl))])
                confirm_dialog("nhap", new_data)
    with t2:
        f = st.file_uploader("Nạp file Excel Nhập", type=["xlsx"])
        if f and st.button("🚀 Đồng bộ Excel lên Cloud"):
            df_ex = pd.read_excel(f)
            df_ex['ID_He_Thong'] = [f"TN-EX-{uuid.uuid4().hex[:6].upper()}" for _ in range(len(df_ex))]
            df_ex['Thoi_Gian_Tao'] = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            confirm_dialog("nhap", df_ex)

# C. CẤP PHÁT
elif menu == "🚚 Cấp Phát":
    st.header("Cấp Phát Về Đội")
    tu_k = st.selectbox("Từ kho", CO_SO)
    lvt_c = st.selectbox("Loại VT", list(DANM_MUC_NCC.keys()))
    models = st.session_state.inventory[(st.session_state.inventory['Vị_Trí_Kho'] == tu_k) & (st.session_state.inventory['Loại_VT'] == lvt_c)]['Mã_TB'].unique()
    with st.form("f_cap"):
        m_c = st.selectbox("Model", models if len(models)>0 else ["Trống"])
        den, sl_c = st.selectbox("Đến Đội", DANH_SACH_14_DOI), st.number_input("Số lượng cấp", min_value=1)
        if st.form_submit_button("🚀 Thực hiện Cấp"):
            confirm_dialog("cap_phat", pd.DataFrame([{'Từ_Kho': tu_k, 'Mã_TB': m_c, 'Số_Lượng': sl_c, 'Đến_Đơn_Vị': den}]))

# D. HIỆN TRƯỜNG
elif menu == "🛠️ Hiện trường (Seri)":
    st.header(f"Cập nhật Đội: {st.session_state.user_name}")
    df_dv = st.session_state.inventory[st.session_state.inventory['Vị_Trí_Kho'] == st.session_state.user_name]
    if not df_dv.empty:
        ed = st.data_editor(df_dv[['ID_He_Thong', 'Mã_TB', 'Số_Seri', 'Trạng_Thái_Luoi', 'Mục_Đích', 'Vị_Tiết_Chi_Tiết']],
            column_config={"Trạng_Thái_Luoi": st.column_config.SelectboxColumn("TT", options=TRANG_THAI_LIST), "Mục_Đích": st.column_config.SelectboxColumn("Vị trí", options=MUC_DICH_LIST)},
            disabled=['ID_He_Thong', 'Mã_TB'], use_container_width=True)
        if st.button("💾 Lưu Cloud"): confirm_dialog("hien_truong", ed)
    else: st.warning("Kho Đội trống.")

# E. BÁO HỎNG & DUYỆT HỎNG
elif menu == "🚨 Báo Hỏng":
    st.header("Gửi Yêu Cầu Báo Hỏng")
    with st.form("f_h"):
        lvt = st.selectbox("Loại", list(DANM_MUC_NCC.keys()))
        tvt, ncc = st.text_input("Tên vật tư"), st.selectbox("Nhà CC", DANM_MUC_NCC[lvt])
        cl, sl = st.text_input("Model"), st.number_input("SL", min_value=1)
        if st.form_submit_button("🚀 Gửi báo hỏng"):
            now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            confirm_dialog("bao_hong", pd.DataFrame([{'Thời_Gian_Báo': now, 'Đơn_Vị': st.session_state.user_name, 'Loại_VT': lvt, 'Tên_Vật_Tư': tvt, 'Nhà_CC': ncc, 'Chủng_Loại': cl, 'Số_Lượng': sl, 'Lý_Do': 'Hỏng', 'Trạng_Thái': 'Chờ xử lý', 'Thời_Gian_Bù': '---'}]))

elif menu == "🚨 Duyệt Báo Hỏng":
    st.header("Phê Duyệt Bù Hàng")
    if not st.session_state.requests.empty:
        req_df = st.session_state.requests.copy(); req_df.insert(0, "Duyệt", False)
        ed_h = st.data_editor(req_df, use_container_width=True, disabled=req_df.columns[1:])
        idx = ed_h[ed_h["Duyệt"] == True].index.tolist()
        if idx and st.button("✅ Xác nhận bù hàng"): confirm_dialog("duyet_hong", idx)
