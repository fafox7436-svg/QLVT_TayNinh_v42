import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import plotly.express as px
import datetime
import io
import uuid

# --- 1. THIẾT LẬP HỆ THỐNG ---
st.set_page_config(page_title="Hệ thống QLVT PC Tây Ninh - v42 Ultra", layout="wide")
NAM_HIEN_TAI = datetime.datetime.now().year

# Danh mục đầy đủ không cắt xén
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

# --- 2. KẾT NỐI DỮ LIỆU CLOUD ---
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
        conn.update(worksheet="inventory", data=st.session_state.inventory, validate=False)
        conn.update(worksheet="requests", data=st.session_state.requests, validate=False)

# --- 3. XỬ LÝ NGHIỆP VỤ (DIALOG) ---
@st.dialog("XÁC NHẬN NGHIỆP VỤ")
def confirm_dialog(action, data=None):
    st.warning("⚠️ Dữ liệu sẽ được ghi vĩnh viễn lên Google Sheets.")
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
        st.success("Thành công!"); st.rerun()

# --- 4. GIAO DIỆN ĐĂNG NHẬP ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if not st.session_state.logged_in:
    st.markdown("<h1 style='text-align:center;'>🌐 QUẢN LÝ VẬT TƯ PC TÂY NINH</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,1.5,1])
    with c2:
        u = st.selectbox("Tài khoản đơn vị", ["admin"] + DANH_SACH_14_DOI)
        p = st.text_input("Mật khẩu", type="password")
        if st.button("🔓 Đăng nhập hệ thống", use_container_width=True):
            if p == USER_DB.get(u):
                st.session_state.logged_in, st.session_state.user_role, st.session_state.user_name = True, ("admin" if u=="admin" else "doi"), u
                st.rerun()
            else: st.error("Sai mật khẩu!")
    st.stop()

# --- 5. MENU ĐIỀU HƯỚNG ---
st.sidebar.markdown(f"### Chào: {st.session_state.user_name}")
if st.sidebar.button("🚪 Đăng xuất"): st.session_state.logged_in = False; st.rerun()

if st.session_state.user_role == "admin":
    menu = st.sidebar.radio("CHỨC NĂNG ADMIN", ["📊 Dashboard & Quản lý", "📥 Nhập kho & Đổ Excel", "🚚 Cấp phát về Đội", "🚨 Duyệt báo hỏng"])
else:
    menu = st.sidebar.radio("CHỨC NĂNG ĐỘI", ["🛠️ Cập nhật hiện trường", "🚨 Báo hỏng thiết bị"])

# --- 6. CHI TIẾT CÁC CHỨC NĂNG ---

# A. DASHBOARD
if menu == "📊 Dashboard & Quản lý":
    st.header("📊 Tổng quan vật tư lưới điện")
    df = st.session_state.inventory.copy()
    if not df.empty:
        c1, c2 = st.columns(2)
        with c1: st.plotly_chart(px.pie(df, names='Trạng_Thái_Luoi', title="Tỷ lệ Trên lưới/Dưới kho", hole=.4), use_container_width=True)
        with c2: st.plotly_chart(px.bar(df.groupby(['Vị_Trí_Kho', 'Trạng_Thái_Luoi']).size().reset_index(name='SL'), x='Vị_Trí_Kho', y='SL', color='Trạng_Thái_Luoi', barmode='group', title="Phân bổ vật tư theo đơn vị"), use_container_width=True)
        
        st.subheader("📋 Bảng quản lý chi tiết")
        df.insert(0, "Xóa", False)
        ed = st.data_editor(df, use_container_width=True, hide_index=True)
        to_del = ed[ed["Xóa"] == True]["ID_He_Thong"].tolist()
        if to_del and st.button("🗑️ Xác nhận xóa vĩnh viễn trên Cloud"): confirm_dialog("xoa", to_del)
    else: st.info("Dữ liệu trống.")

# B. NHẬP KHO & ĐỔ EXCEL
elif menu == "📥 Nhập kho & Đổ Excel":
    st.header("📥 Tiếp nhận vật tư mới")
    t1, t2 = st.tabs(["✍️ Nhập tay", "📁 Đổ dữ liệu từ Excel"])
    
    with t1:
        # Code nhập tay (đã có ở bản trước)
        pass 

    with t2:
        st.subheader("📁 Nạp dữ liệu Tiếp nhận hàng loạt")
        st.info("Tải file Excel có các cột: Loại_VT, Nhà_CC, Mã_TB, Năm_SX, Nguồn_Nhap, Vị_Trí_Kho")
        f_ex = st.file_uploader("Chọn file Excel tiếp nhận", type=["xlsx"], key="upload_nhap")
        
        if f_ex:
            df_upload = pd.read_excel(f_ex).astype(str)
            st.write("Dữ liệu xem trước:")
            st.dataframe(df_upload.head(), use_container_width=True)
            
            if st.button("📥 Xác nhận nạp dữ liệu vào Kho Tổng"):
                # Tự động tạo mã hệ thống và thời gian
                df_upload['ID_He_Thong'] = [f"TN-{uuid.uuid4().hex[:8].upper()}" for _ in range(len(df_upload))]
                df_upload['Thoi_Gian_Tao'] = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                
                # Đảm bảo các cột hiện trường không bị trống để tránh lỗi app Đội
                for col in ['Số_Seri', 'Trạng_Thái_Luoi', 'Mục_Đích', 'Vị_Tiết_Chi_Tiết']:
                    if col not in df_upload.columns:
                        df_upload[col] = 'Chưa nhập' if col == 'Số_Seri' else ('Dưới kho' if col == 'Trạng_Thái_Luoi' else 'Dự phòng')
                
                confirm_dialog("nhap", df_upload)

# --- MỤC: PHÂN BỔ (CẤP PHÁT) BẰNG EXCEL ---
elif menu == "🚚 Cấp phát về Đội":
    st.header("🚚 Phân bổ vật tư cho 14 Đội")
    t1, t2 = st.tabs(["✍️ Cấp phát tay", "📁 Đổ Excel phân bổ"])
    
    with t1:
        # Code cấp phát tay (đã có ở bản trước)
        pass

    with t2:
        st.subheader("📁 Nạp file Excel phân bổ hàng loạt")
        f_cap_ex = st.file_uploader("Chọn file Excel phân bổ", type=["xlsx"], key="upload_cap")
        
        if f_cap_ex:
            df_cap = pd.read_excel(f_cap_ex).astype(str)
            st.write("Xem trước danh sách phân bổ:")
            st.dataframe(df_cap, use_container_width=True)
            
            if st.button("🚀 Thực hiện Phân bổ hàng loạt"):
                # Logic này sẽ lặp qua từng dòng trong Excel để cập nhật vị trí kho
                confirm_dialog("cap_phat", df_cap)

# C. CẤP PHÁT
elif menu == "🚚 Cấp phát về Đội":
    st.header("🚚 Điều động vật tư cho 14 Đội")
    c1, c2 = st.columns(2)
    with c1: tu_k = st.selectbox("Từ kho xuất", CO_SO)
    with c2: lvt_c = st.selectbox("Loại vật tư cần cấp", list(DANM_MUC_NCC.keys()))
    
    avai = st.session_state.inventory[(st.session_state.inventory['Vị_Trí_Kho'] == tu_k) & (st.session_state.inventory['Loại_VT'] == lvt_c)]
    
    with st.form("f_cap"):
        m_c = st.selectbox("Model thiết bị", avai['Mã_TB'].unique() if not avai.empty else ["Hết hàng"])
        den = st.selectbox("Cấp về Đội", DANH_SACH_14_DOI)
        sl_max = len(avai[avai['Mã_TB'] == m_c])
        sl_c = st.number_input(f"Số lượng cấp (Hiện có: {sl_max})", min_value=0, max_value=sl_max if sl_max > 0 else 0)
        if st.form_submit_button("🚀 Thực hiện điều động"):
            if sl_c > 0: confirm_dialog("cap_phat", pd.DataFrame([{'Từ_Kho': tu_k, 'Mã_TB': m_c, 'Số_Lượng': sl_c, 'Đến_Đơn_Vị': den}]))

# D. HIỆN TRƯỜNG
elif menu == "🛠️ Cập nhật hiện trường":
    st.header(f"🛠️ Đơn vị: {st.session_state.user_name}")
    df_dv = st.session_state.inventory[st.session_state.inventory['Vị_Trí_Kho'] == st.session_state.user_name]
    if not df_dv.empty:
        st.info("Nhập số Seri và trạng thái khi lắp đặt thiết bị thực tế.")
        ed = st.data_editor(df_dv[['ID_He_Thong', 'Mã_TB', 'Số_Seri', 'Trạng_Thái_Luoi', 'Mục_Đích', 'Vị_Tiết_Chi_Tiết']],
            column_config={
                "Trạng_Thái_Luoi": st.column_config.SelectboxColumn("Trạng thái", options=TRANG_THAI_LIST),
                "Mục_Đích": st.column_config.SelectboxColumn("Mục đích", options=MUC_DICH_LIST)
            },
            disabled=['ID_He_Thong', 'Mã_TB'], use_container_width=True, hide_index=True)
        if st.button("💾 Lưu tất cả thay đổi lên Cloud"): confirm_dialog("hien_truong", ed)
    else: st.warning("Kho của Đội hiện đang trống.")

# E. BÁO HỎNG & DUYỆT BÙ
elif menu == "🚨 Báo hỏng thiết bị":
    st.header("🚨 Gửi yêu cầu bù hàng")
    with st.form("f_h"):
        lvt_h = st.selectbox("Loại vật tư hỏng", list(DANM_MUC_NCC.keys()))
        tvt_h = st.text_input("Model/Chủng loại hỏng")
        ncc_h = st.selectbox("Nhà sản xuất", DANM_MUC_NCC[lvt_h])
        sl_h = st.number_input("Số lượng", min_value=1)
        ld_h = st.text_area("Tình trạng hỏng chi tiết")
        if st.form_submit_button("🚨 Gửi báo hỏng"):
            confirm_dialog("bao_hong", pd.DataFrame([{'Thời_Gian_Báo': datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S"), 'Đơn_Vị': st.session_state.user_name, 'Loại_VT': lvt_h, 'Tên_Vật_Tư': tvt_h, 'Nhà_CC': ncc_h, 'Chủng_Loại': '---', 'Số_Lượng': sl_h, 'Lý_Do': ld_h, 'Trạng_Thái': 'Chờ xử lý', 'Thời_Gian_Bù': '---'}]))

elif menu == "🚨 Duyệt báo hỏng":
    st.header("🚨 Phê duyệt yêu cầu bù hàng")
    if not st.session_state.requests.empty:
        df_r = st.session_state.requests.copy()
        df_r.insert(0, "Duyệt", False)
        ed_r = st.data_editor(df_r, use_container_width=True, hide_index=True, disabled=df_r.columns[1:])
        idx_duyet = ed_r[ed_r["Duyệt"] == True].index.tolist()
        if idx_duyet and st.button("✅ Xác nhận đã bù hàng"): confirm_dialog("duyet_hong", idx_duyet)
    else: st.info("Không có yêu cầu nào.")

