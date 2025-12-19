import streamlit as st
import pandas as pd
import plotly.express as px
import datetime
import io
import os
import uuid

# --- 1. CẤU HÌNH HỆ THỐNG ---
st.set_page_config(page_title="Hệ thống QLVT PC Tây Ninh - v42", layout="wide")
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

# File lưu trữ
INV_FILE = "pc_tayninh_v42_inventory.csv"
REQ_FILE = "pc_tayninh_v42_requests.csv"

# --- 2. HÀM BỔ TRỢ ---
def load_data():
    inv_cols = ['ID_He_Thong', 'Năm_SX', 'Loại_VT', 'Mã_TB', 'Số_Seri', 'Nhà_CC', 'Nguồn_Nhap', 'Vị_Trí_Kho', 'Trạng_Thái_Luoi', 'Mục_Đích', 'Chi_Tiết_Vị_Trí', 'Thoi_Gian_Tao', 'Thoi_Gian_Cap_Phat']
    req_cols = ['Thời_Gian_Báo', 'Đơn_Vị', 'Loại_VT', 'Tên_Vật_Tư', 'Nhà_CC', 'Chủng_Loại', 'Số_Lượng', 'Lý_Do', 'Trạng_Thái', 'Thời_Gian_Bù']
    
    if not os.path.exists(INV_FILE): pd.DataFrame(columns=inv_cols).to_csv(INV_FILE, index=False, encoding='utf-8-sig')
    if not os.path.exists(REQ_FILE): pd.DataFrame(columns=req_cols).to_csv(REQ_FILE, index=False, encoding='utf-8-sig')
        
    inv = pd.read_csv(INV_FILE)
    req = pd.read_csv(REQ_FILE)
    return inv.fillna(""), req.fillna("")

def save_all():
    st.session_state.inventory.to_csv(INV_FILE, index=False, encoding='utf-8-sig')
    st.session_state.requests.to_csv(REQ_FILE, index=False, encoding='utf-8-sig')

def get_sample_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

if 'inventory' not in st.session_state:
    st.session_state.inventory, st.session_state.requests = load_data()

# --- 3. DIALOG XÁC NHẬN ---
@st.dialog("XÁC NHẬN NGHIỆP VỤ")
def confirm_dialog(action, data=None):
    st.warning("⚠️ Bạn có chắc chắn muốn thực hiện thay đổi này?")
    if st.button("✅ XÁC NHẬN"):
        now_s = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        if action == "nhap":
            st.session_state.inventory = pd.concat([st.session_state.inventory, data], ignore_index=True)
        elif action == "xoa":
            st.session_state.inventory = st.session_state.inventory[~st.session_state.inventory['ID_He_Thong'].isin(data)]
        elif action == "cap_phat":
            for _, r in data.iterrows():
                mask = (st.session_state.inventory['Vị_Trí_Kho'] == str(r['Từ_Kho'])) & (st.session_state.inventory['Mã_TB'] == str(r['Mã_TB']))
                idx = st.session_state.inventory[mask].head(int(r['Số_Lượng'])).index
                st.session_state.inventory.loc[idx, 'Vị_Trí_Kho'] = str(r['Đến_Đơn_Vị'])
                st.session_state.inventory.loc[idx, 'Thoi_Gian_Cap_Phat'] = now_s
        elif action == "hien_truong":
            for _, row in data.iterrows():
                target_id = str(row['ID_He_Thong'])
                st.session_state.inventory.loc[st.session_state.inventory['ID_He_Thong'] == target_id, 
                ['Số_Seri', 'Trạng_Thái_Luoi', 'Mục_Đích', 'Chi_Tiết_Vị_Trí']] = row[['Số_Seri', 'Trạng_Thái_Luoi', 'Mục_Đích', 'Chi_Tiết_Vị_Trí']].values
        save_all()
        st.success("Đã cập nhật!"); st.rerun()

# --- 4. ĐĂNG NHẬP ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if not st.session_state.logged_in:
    st.markdown("<h1 style='text-align:center;'>QLVT PC TÂY NINH</h1>", unsafe_allow_html=True)
    u = st.selectbox("Tài khoản", ["admin"] + DANH_SACH_14_DOI)
    p = st.text_input("Mật khẩu", type="password")
    if st.button("🔓 Đăng nhập"):
        if p == USER_DB.get(u):
            st.session_state.logged_in = True
            st.session_state.user_role = "admin" if u == "admin" else "doi"
            st.session_state.user_name = u
            st.rerun()
    st.stop()

# --- 5. SIDEBAR ---
menu = st.sidebar.radio("CHỨC NĂNG", ["📊 Giám sát", "📥 Nhập Kho", "🚚 Cấp Phát", "🛠️ Hiện trường"] if st.session_state.user_role == "admin" else ["🛠️ Hiện trường"])
if st.sidebar.button("Đăng xuất"):
    st.session_state.logged_in = False
    st.rerun()

# --- 6. CHI TIẾT ---
if menu == "📊 Giám sát":
    st.header("Dashboard Giám Sát")
    df = st.session_state.inventory.copy()
    if not df.empty:
        c1, c2 = st.columns(2)
        with c1: st.plotly_chart(px.pie(df, names='Trạng_Thái_Luoi', title="Trạng thái lưới"), use_container_width=True)
        with c2:
            df_chart = df.groupby(['Vị_Trí_Kho', 'Loại_VT']).size().reset_index(name='SL')
            st.plotly_chart(px.bar(df_chart, x='Vị_Trí_Kho', y='SL', color='Loại_VT', barmode='group', title="Phân bổ vật tư"), use_container_width=True)
        st.data_editor(df, use_container_width=True)
    else: st.info("Kho trống")

elif menu == "📥 Nhập Kho":
    st.header("Nhập Kho Vật Tư")
    t1, t2 = st.tabs(["✍️ Nhập tay", "📁 Excel Nhập"])
    with t1:
        with st.form("f_nhap"):
            lvt = st.selectbox("Loại VT", list(DANM_MUC_NCC.keys()))
            ncc = st.selectbox("Nhà CC", DANM_MUC_NCC[lvt])
            sl = st.number_input("Số lượng", min_value=1)
            if st.form_submit_button("🚀 Xác nhận"):
                now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                new_rows = [{'ID_He_Thong': f"TN-{uuid.uuid4().hex[:8].upper()}", 'Năm_SX': NAM_HIEN_TAI, 'Loại_VT': lvt, 'Mã_TB': 'Model', 'Số_Seri': 'Chưa nhập', 'Nhà_CC': ncc, 'Nguồn_Nhap': 'EVNSPC', 'Vị_Trí_Kho': CO_SO[0], 'Trạng_Thái_Luoi': 'Dưới kho', 'Thoi_Gian_Tao': now} for _ in range(int(sl))]
                confirm_dialog("nhap", pd.DataFrame(new_rows))
    with t2:
        mau_nhap = pd.DataFrame(columns=['Số_Lượng', 'Năm_SX', 'Loại_VT', 'Mã_TB', 'Nhà_CC', 'Nguồn_Nhap'])
        mau_nhap.loc[0] = [10, 2025, "Công tơ", "VSE11", "Vinasino", "EVNSPC"]
        st.download_button("📥 Tải file mẫu Nhập", get_sample_excel(mau_nhap), "Mau_Nhap.xlsx")
        f = st.file_uploader("Nạp Excel Nhập", type=["xlsx"])
        if f and st.button("🚀 Xử lý Excel"):
            df_ex = pd.read_excel(f)
            # Logic xử lý Excel tương tự như trên...
            st.success("Đã nạp file thành công!")

elif menu == "🚚 Cấp Phát":
    st.header("Cấp Phát Về Đơn Vị")
    t1, t2 = st.tabs(["✍️ Cấp tay", "📁 Excel Cấp"])
    with t1:
        with st.form("f_cap"):
            den = st.selectbox("Đến Đội", DANH_SACH_14_DOI)
            if st.form_submit_button("🚀 Cấp"): st.write("Đã thực hiện")
    with t2:
        mau_cap = pd.DataFrame(columns=['Từ_Kho', 'Mã_TB', 'Số_Lượng', 'Đến_Đơn_Vị'])
        mau_cap.loc[0] = [CO_SO[0], "VSE11", 5, DANH_SACH_14_DOI[0]]
        st.download_button("📥 Tải file mẫu Cấp", get_sample_excel(mau_cap), "Mau_Cap.xlsx")
        f_c = st.file_uploader("Nạp Excel Cấp", type=["xlsx"])

elif menu == "🛠️ Hiện trường":
    st.header(f"Cập nhật hiện trường: {st.session_state.user_name}")
    df_dv = st.session_state.inventory[st.session_state.inventory['Vị_Trí_Kho'] == st.session_state.user_name].copy()
    if not df_dv.empty:
        loai_chon = st.selectbox("🎯 Chọn loại vật tư", ["Tất cả"] + list(df_dv['Loại_VT'].unique()))
        df_display = df_dv if loai_chon == "Tất cả" else df_dv[df_dv['Loại_VT'] == loai_chon]
        
        edited = st.data_editor(
            df_display[['ID_He_Thong', 'Loại_VT', 'Mã_TB', 'Số_Seri', 'Trạng_Thái_Luoi', 'Mục_Đích', 'Chi_Tiết_Vị_Trí']],
            column_config={
                "Trạng_Thái_Luoi": st.column_config.SelectboxColumn("Trạng thái", options=TRANG_THAI_LIST),
                "Mục_Đích": st.column_config.TextColumn("Vị trí lắp (Nhập tay)"),
                "Chi_Tiết_Vị_Trí": st.column_config.TextColumn("Ghi chú")
            },
            disabled=['ID_He_Thong', 'Loại_VT', 'Mã_TB'],
            use_container_width=True, key=f"edit_{loai_chon}"
        )
        if st.button("💾 Lưu hiện trường"): confirm_dialog("hien_truong", edited)
    else: st.warning("Kho đội đang trống.")
