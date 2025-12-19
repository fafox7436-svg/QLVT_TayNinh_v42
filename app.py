import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import datetime
import io
import uuid

# --- 1. CẤU HÌNH HỆ THỐNG ---
st.set_page_config(page_title="Hệ thống QLVT PC Tây Ninh - v42 Siêu Đầy Đủ", layout="wide")
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
        # validate=False giúp tránh lỗi định dạng A1 cell khi dữ liệu lớn/trống
        conn.update(worksheet="inventory", data=st.session_state.inventory, validate=False)
        conn.update(worksheet="requests", data=st.session_state.requests, validate=False)

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
            for i in data:
                st.session_state.requests.loc[i, 'Trạng_Thái'] = "Đã bù hàng"
                st.session_state.requests.loc[i, 'Thời_Gian_Bù'] = now_s
        elif action == "xoa":
            st.session_state.inventory = st.session_state.inventory[~st.session_state.inventory['ID_He_Thong'].isin(data)]
            
        sync_to_cloud()
        st.success("Cập nhật thành công!"); st.rerun()

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
    menu = st.sidebar.radio("QUẢN TRỊ CÔNG TY", ["📊 Dashboard & Quản lý", "📥 Nhập Vật Tư", "🚚 Cấp Phát Về Đội", "🚨 Duyệt Báo Hỏng"])
else:
    menu = st.sidebar.radio("GIAO DIỆN ĐỘI", ["🛠️ Cập nhật Hiện trường", "🚨 Báo Hỏng Thiết Bị"])

# --- 6. CHI TIẾT CHỨC NĂNG ---

# A. DASHBOARD
if menu == "📊 Dashboard & Quản lý":
    st.header("Dashboard Giám Sát Vật Tư")
    df = st.session_state.inventory.copy()
    if not df.empty:
        c1, c2 = st.columns(2)
        with c1: st.plotly_chart(px.pie(df, names='Trạng_Thái_Luoi', title="Trạng thái thiết bị"), use_container_width=True)
        with c2: st.plotly_chart(px.bar(df.groupby(['Vị_Trí_Kho', 'Trạng_Thái_Luoi']).size().reset_index(name='SL'), x='Vị_Trí_Kho', y='SL', color='Trạng_Thái_Luoi', title="Vật tư theo đơn vị"), use_container_width=True)
        
        st.subheader("Bảng dữ liệu tổng hợp (Admin có quyền xóa)")
        df.insert(0, "Chọn xóa", False)
        ed = st.data_editor(df, use_container_width=True, hide_index=True)
        to_del = ed[ed["Chọn xóa"] == True]["ID_He_Thong"].tolist()
        if to_del and st.button("🗑️ Xóa dòng đã chọn trên Cloud"): confirm_dialog("xoa", to_del)
    else: st.info("Hiện chưa có dữ liệu vật tư.")

# B. NHẬP KHO (BAO GỒM ĐỔ EXCEL)
elif menu == "📥 Nhập Vật Tư":
    st.header("Nhập Kho Vật Tư")
    t1, t2 = st.tabs(["✍️ Nhập tay thủ công", "📁 Đổ dữ liệu từ Excel"])
    
    with t1:
        # Tách chọn Loại VT ra ngoài để cập nhật NCC ngay lập tức
        lvt = st.selectbox("Chọn Loại vật tư", list(DANM_MUC_NCC.keys()), key="nhap_lvt")
        with st.form("f_nhap_tay"):
            ncc = st.selectbox("Nhà cung cấp", DANM_MUC_NCC[lvt])
            c1, c2 = st.columns(2)
            with c1:
                ng = st.selectbox("Nguồn nhập", NGUON_NHAP_NGOAI)
                kh = st.selectbox("Nhập vào kho", CO_SO)
            with c2:
                mod = st.text_input("Model thiết bị")
                sl = st.number_input("Số lượng nhập", min_value=1, step=1)
            
            if st.form_submit_button("🚀 Xác nhận Nhập tay"):
                now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                new_data = pd.DataFrame([{
                    'ID_He_Thong': f"TN-{uuid.uuid4().hex[:8].upper()}", 
                    'Năm_SX': NAM_HIEN_TAI, 'Loại_VT': lvt,
                    'Mã_TB': mod, 'Số_Seri': 'Chưa nhập', 'Nhà_CC': ncc, 
                    'Nguồn_Nhap': ng, 'Vị_Trí_Kho': kh,
                    'Trạng_Thái_Luoi': 'Dưới kho', 'Mục_Đích': 'Dự phòng', 
                    'Vị_Tiết_Chi_Tiết': 'Tại kho', 'Thoi_Gian_Tao': now
                } for _ in range(int(sl))])
                confirm_dialog("nhap", new_data)

    with t2:
        st.subheader("Nạp dữ liệu từ file Excel")
        st.info("Tải file Excel (.xlsx) có các cột: Loại_VT, Nhà_CC, Mã_TB, Năm_SX, Nguồn_Nhap, Vị_Trí_Kho")
        
        file_ex = st.file_uploader("Chọn file Excel mẫu của bạn", type=["xlsx"])
        
        if file_ex:
            # Đọc dữ liệu từ Excel
            df_upload = pd.read_excel(file_ex).astype(str)
            
            st.write("🔍 Xem trước 5 dòng dữ liệu từ file của bạn:")
            st.dataframe(df_upload.head(), use_container_width=True)
            
            if st.button("📥 XÁC NHẬN ĐẨY TẤT CẢ LÊN CLOUD"):
                # Tự động bổ sung các cột hệ thống còn thiếu
                if 'ID_He_Thong' not in df_upload.columns:
                    df_upload['ID_He_Thong'] = [f"TN-EX-{uuid.uuid4().hex[:6].upper()}" for _ in range(len(df_upload))]
                
                df_upload['Thoi_Gian_Tao'] = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                
                # Đảm bảo các cột mặc định cho Hiện trường không bị trống
                if 'Số_Seri' not in df_upload.columns: df_upload['Số_Seri'] = 'Chưa nhập'
                if 'Trạng_Thái_Luoi' not in df_upload.columns: df_upload['Trạng_Thái_Luoi'] = 'Dưới kho'
                if 'Mục_Đích' not in df_upload.columns: df_upload['Mục_Đích'] = 'Dự phòng tại kho'
                
                confirm_dialog("nhap", df_upload)

# C. CẤP PHÁT
elif menu == "🚚 Cấp Phát Về Đội":
    st.header("Điều động vật tư về 14 Đội")
    c1, c2 = st.columns(2)
    with c1: tu_k = st.selectbox("Từ kho xuất", CO_SO)
    with c2: lvt_c = st.selectbox("Loại vật tư cấp", list(DANM_MUC_NCC.keys()))
    
    available = st.session_state.inventory[(st.session_state.inventory['Vị_Trí_Kho'] == tu_k) & (st.session_state.inventory['Loại_VT'] == lvt_c)]
    models = available['Mã_TB'].unique()
    
    with st.form("f_cap"):
        m_c = st.selectbox("Chọn Model thiết bị", models if len(models)>0 else ["Không còn hàng trong kho"])
        den = st.selectbox("Cấp về đơn vị/Đội", DANH_SACH_14_DOI)
        max_sl = len(available[available['Mã_TB'] == m_c])
        sl_c = st.number_input(f"Số lượng cấp (Tối đa: {max_sl})", min_value=0, max_value=max_sl if max_sl > 0 else 0)
        
        if st.form_submit_button("🚀 Thực hiện Cấp phát"):
            if sl_c > 0:
                confirm_dialog("cap_phat", pd.DataFrame([{'Từ_Kho': tu_k, 'Mã_TB': m_c, 'Số_Lượng': sl_c, 'Đến_Đơn_Vị': den}]))
            else: st.error("Vui lòng nhập số lượng hợp lệ.")

# D. HIỆN TRƯỜNG (CHO ĐỘI)
elif menu == "🛠️ Cập nhật Hiện trường":
    st.header(f"Giao diện Đội: {st.session_state.user_name}")
    df_dv = st.session_state.inventory[st.session_state.inventory['Vị_Trí_Kho'] == st.session_state.user_name]
    if not df_dv.empty:
        st.write("Hướng dẫn: Nhập số Seri thiết bị và chuyển trạng thái khi lắp đặt xong.")
        ed = st.data_editor(df_dv[['ID_He_Thong', 'Mã_TB', 'Số_Seri', 'Trạng_Thái_Luoi', 'Mục_Đích', 'Vị_Tiết_Chi_Tiết']],
            column_config={
                "Trạng_Thái_Luoi": st.column_config.SelectboxColumn("Trạng thái", options=TRANG_THAI_LIST),
                "Mục_Đích": st.column_config.SelectboxColumn("Mục đích lắp", options=MUC_DICH_LIST)
            },
            disabled=['ID_He_Thong', 'Mã_TB'], use_container_width=True, hide_index=True)
        if st.button("💾 Lưu cập nhật lên Cloud"): confirm_dialog("hien_truong", ed)
    else: st.warning("Đội hiện không có vật tư nào trong kho.")

# E. BÁO HỎNG & DUYỆT HỎNG
elif menu == "🚨 Báo Hỏng Thiết Bị":
    st.header("Gửi yêu cầu bù hàng do hỏng")
    with st.form("f_bao_hong"):
        l_h = st.selectbox("Loại vật tư hỏng", list(DANM_MUC_NCC.keys()))
        t_h = st.text_input("Tên/Model thiết bị hỏng")
        ncc_h = st.selectbox("Nhà sản xuất", DANM_MUC_NCC[l_h])
        sl_h = st.number_input("Số lượng hỏng", min_value=1)
        ly_do = st.text_area("Tình trạng/Lý do hỏng")
        if st.form_submit_button("🚨 Gửi yêu cầu"):
            now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            confirm_dialog("bao_hong", pd.DataFrame([{
                'Thời_Gian_Báo': now, 'Đơn_Vị': st.session_state.user_name, 'Loại_VT': l_h, 'Tên_Vật_Tư': t_h, 
                'Nhà_CC': ncc_h, 'Chủng_Loại': '---', 'Số_Lượng': sl_h, 'Lý_Do': ly_do, 'Trạng_Thái': 'Chờ xử lý', 'Thời_Gian_Bù': '---'
            }]))

elif menu == "🚨 Duyệt Báo Hỏng":
    st.header("Quản lý yêu cầu bù hàng từ các Đội")
    if not st.session_state.requests.empty:
        df_req = st.session_state.requests.copy()
        df_req.insert(0, "Duyệt bù", False)
        ed_req = st.data_editor(df_req, use_container_width=True, hide_index=True, disabled=df_req.columns[1:])
        idx_duyet = ed_req[ed_req["Duyệt bù"] == True].index.tolist()
        if idx_duyet and st.button("✅ Xác nhận đã bù hàng cho Đội"):
            confirm_dialog("duyet_hong", idx_duyet)
    else: st.info("Chưa có yêu cầu báo hỏng nào.")

