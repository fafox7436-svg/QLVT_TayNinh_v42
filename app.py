import streamlit as st
import pandas as pd
import plotly.express as px
import datetime
import io
import os
import uuid
import re
from pypdf import PdfReader
# --- HÀM LẤY GIỜ VIỆT NAM (DÙNG CHO TOÀN BỘ APP) ---
def get_vn_time():
    # Lấy giờ hiện tại của server + 7 tiếng
    return (datetime.datetime.now() + datetime.timedelta(hours=7)).strftime("%d/%m/%Y %H:%M:%S")

# --- 1. CẤU HÌNH HỆ THỐNG ---
st.set_page_config(page_title="Hệ thống QLVT PC Tây Ninh - v42 Full Sync GS", layout="wide")
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

# --- 2. HÀM HỖ TRỢ EXCEL ---
def get_sample_excel(df):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    return output.getvalue()

# --- 3. QUẢN LÝ DỮ LIỆU (SUPABASE) ---
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool
import streamlit as st

def get_engine():
    conf = st.secrets["connections"]["supabase"]
    
    # Tạo chuỗi kết nối từ các thông số mới
    USER = conf["user"]
    PASSWORD = conf["password"]
    HOST = conf["host"]
    PORT = conf["port"]
    DBNAME = conf["dbname"]

    # Sử dụng aws-1 và cổng 6543
    DATABASE_URL = f"postgresql+psycopg2://{USER}:{PASSWORD}@{HOST}:{PORT}/{DBNAME}?sslmode=require"

    # NullPool là bắt buộc khi dùng Transaction Pooler để tránh treo App
    return create_engine(DATABASE_URL, poolclass=NullPool)

# --- HÀM GHI NHẬT KÝ HOẠT ĐỘNG ---
def luu_nhat_ky(hanh_dong, noi_dung):
    try:
        engine = get_engine()
        # SỬA DÒNG NÀY: Dùng hàm get_vn_time()
        now = get_vn_time() 
        
        user = st.session_state.user_name if 'user_name' in st.session_state else "Unknown"
        
        log_df = pd.DataFrame([{
            'thoi_gian': now,
            'nguoi_thuc_hien': user,
            'hanh_dong': hanh_dong,
            'noi_dung_chi_tiet': noi_dung
        }])
        
        # Dùng 'append' để ghi nối tiếp, không xóa dữ liệu cũ
        with engine.begin() as conn:
            log_df.to_sql('nhat_ky_he_thong', conn, if_exists='append', index=False)
            
    except Exception as e:
        print(f"Lỗi ghi nhật ký: {e}")

def load_data():
    # Định nghĩa danh sách cột chuẩn của App (Có dấu, viết hoa)
    inv_cols = ['ID_He_Thong', 'Năm_SX', 'Loại_VT', 'Mã_TB', 'Số_Seri', 'Nhà_CC', 'Nguồn_Nhap', 'Vị_Trí_Kho', 'Trạng_Thái_Luoi', 'Mục_Đích', 'Chi_Tiết_Vị_Trí', 'Thoi_Gian_Tao', 'Thoi_Gian_Cap_Phat']
    req_cols = ['ID', 'Thời_Gian_Báo', 'Đơn_Vị', 'Loại_VT', 'Tên_Vật_Tư', 'Nhà_CC', 'Chủng_Loại', 'Số_Lượng', 'Lý_Do', 'Trạng_Thái', 'Thời_Gian_Bù']
    
    engine = get_engine()
    try:
        # Đọc dữ liệu thô từ SQL (tên cột sẽ là: id_he_thong, ma_tb...)
        inv_raw = pd.read_sql("SELECT * FROM inventory", engine)
        req_raw = pd.read_sql("SELECT * FROM requests", engine)
        
        # --- BƯỚC SỬA LỖI KEYERROR: Đổi tên cột thủ công ---
        # Map từ tên SQL sang tên App
        map_inv = {
            'id_he_thong': 'ID_He_Thong', 'nam_sx': 'Năm_SX', 'loai_vt': 'Loại_VT', 
            'ma_tb': 'Mã_TB', 'so_seri': 'Số_Seri', 'nha_cc': 'Nhà_CC', 
            'nguon_nhap': 'Nguồn_Nhap', 'vi_tri_kho': 'Vị_Trí_Kho', 
            'trang_thai_luoi': 'Trạng_Thái_Luoi', 'muc_dich': 'Mục_Đích', 
            'chi_tiet_vi_tri': 'Chi_Tiết_Vị_Trí', 'thoi_gian_tao': 'Thoi_Gian_Tao', 
            'thoi_gian_cap_phat': 'Thoi_Gian_Cap_Phat'
        }
        
        map_req = {
            'id': 'ID', 'thoi_gian_bao': 'Thời_Gian_Báo', 'don_vi': 'Đơn_Vị',
            'loai_vt': 'Loại_VT', 'ten_vat_tu': 'Tên_Vật_Tư', 'nha_cc': 'Nhà_CC',
            'chung_loai': 'Chủng_Loại', 'so_luong': 'Số_Lượng', 'ly_do': 'Lý_Do',
            'trang_thai': 'Trạng_Thái', 'thoi_gian_bu': 'Thời_Gian_Bù'
        }

        # Thực hiện đổi tên cột
        inv_raw.rename(columns=map_inv, inplace=True)
        req_raw.rename(columns=map_req, inplace=True)
        
        # Đảm bảo đủ cột (tránh lỗi nếu SQL thiếu cột)
        for c in inv_cols:
            if c not in inv_raw.columns: inv_raw[c] = ""
            
        for c in req_cols:
            if c not in req_raw.columns: req_raw[c] = ""

        # Trả về đúng thứ tự cột
        return inv_raw[inv_cols].fillna(""), req_raw[req_cols].fillna("")

    except Exception as e:
        st.error(f"Lỗi load data: {e}")
        # Trả về bảng rỗng với tên cột ĐÚNG CHUẨN để không bị lỗi KeyError
        return pd.DataFrame(columns=inv_cols), pd.DataFrame(columns=req_cols)

# --- BỔ SUNG HÀM LƯU DỮ LIỆU (QUAN TRỌNG) ---
def save_all():
    engine = get_engine()
    # Chuyển tên cột về viết thường (SQL chuẩn)
    inv_save = st.session_state.inventory.copy()
    # Map ngược từ Tên App -> Tên SQL
    map_inv_inv = {
        'ID_He_Thong': 'id_he_thong', 'Năm_SX': 'nam_sx', 'Loại_VT': 'loai_vt', 
        'Mã_TB': 'ma_tb', 'Số_Seri': 'so_seri', 'Nhà_CC': 'nha_cc', 
        'Nguồn_Nhap': 'nguon_nhap', 'Vị_Trí_Kho': 'vi_tri_kho', 
        'Trạng_Thái_Luoi': 'trang_thai_luoi', 'Mục_Đích': 'muc_dich', 
        'Chi_Tiết_Vị_Trí': 'chi_tiet_vi_tri', 'Thoi_Gian_Tao': 'thoi_gian_tao', 
        'Thoi_Gian_Cap_Phat': 'thoi_gian_cap_phat'
    }
    inv_save.rename(columns=map_inv_inv, inplace=True)
    
    req_save = st.session_state.requests.copy()
    if 'ID' in req_save.columns: req_save = req_save.drop(columns=['ID'])
    map_req_inv = {
        'Thời_Gian_Báo': 'thoi_gian_bao', 'Đơn_Vị': 'don_vi',
        'Loại_VT': 'loai_vt', 'Tên_Vật_Tư': 'ten_vat_tu', 'Nhà_CC': 'nha_cc',
        'Chủng_Loại': 'chung_loai', 'Số_Lượng': 'so_luong', 'Lý_Do': 'ly_do',
        'Trạng_Thái': 'trang_thai', 'Thời_Gian_Bù': 'thoi_gian_bu'
    }
    req_save.rename(columns=map_req_inv, inplace=True)

    try:
        # Dùng Transaction để đảm bảo an toàn dữ liệu
        with engine.begin() as conn:
            inv_save.to_sql('inventory', conn, if_exists='replace', index=False)
            req_save.to_sql('requests', conn, if_exists='replace', index=False)
    except Exception as e:
        st.error(f"❌ Lỗi lưu dữ liệu: {e}")

# --- KHỞI TẠO DỮ LIỆU (BẮT BUỘC PHẢI CÓ) ---
if 'inventory' not in st.session_state:
    st.session_state.inventory, st.session_state.requests = load_data()

# --- 4. TRUNG TÂM XÁC NHẬN ---
@st.dialog("XÁC NHẬN NGHIỆP VỤ")
def confirm_dialog(action, data=None):
    st.warning("⚠️ Xác nhận thực hiện giao dịch?")
    if st.button("✅ ĐỒNG Ý", use_container_width=True):
        now_s = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        
        if action == "nhap":
            st.session_state.inventory = pd.concat([st.session_state.inventory, data], ignore_index=True)
            # GHI NHẬT KÝ
            sl = len(data)
            loai = data.iloc[0]['Loại_VT'] if not data.empty else ""
            luu_nhat_ky("Nhập kho", f"Nhập mới {sl} {loai} vào {data.iloc[0]['Vị_Trí_Kho']}")
            
        elif action == "xoa":
            st.session_state.inventory = st.session_state.inventory[~st.session_state.inventory['ID_He_Thong'].isin(data)]
            luu_nhat_ky("Xóa dữ liệu", f"Đã xóa vĩnh viễn {len(data)} dòng dữ liệu")
            
        elif action == "cap_phat":
            for _, r in data.iterrows():
                mask = (st.session_state.inventory['Vị_Trí_Kho'] == str(r['Từ_Kho'])) & (st.session_state.inventory['Mã_TB'] == str(r['Mã_TB']))
                idx = st.session_state.inventory[mask].head(int(r['Số_Lượng'])).index
                st.session_state.inventory.loc[idx, 'Vị_Trí_Kho'] = str(r['Đến_Đơn_Vị'])
                st.session_state.inventory.loc[idx, 'Thoi_Gian_Cap_Phat'] = now_s
                
                # GHI NHẬT KÝ
                luu_nhat_ky("Điều chuyển/Cấp phát", f"Chuyển {r['Số_Lượng']} {r['Mã_TB']} từ {r['Từ_Kho']} sang {r['Đến_Đơn_Vị']}")
                
        elif action == "hien_truong":
            for _, row in data.iterrows():
                target_id = str(row['ID_He_Thong'])
                st.session_state.inventory.loc[st.session_state.inventory['ID_He_Thong'] == target_id, 
                ['Số_Seri', 'Trạng_Thái_Luoi', 'Mục_Đích', 'Chi_Tiết_Vị_Trí']] = row[['Số_Seri', 'Trạng_Thái_Luoi', 'Mục_Đích', 'Chi_Tiết_Vị_Trí']].values
            
            luu_nhat_ky("Cập nhật hiện trường", f"Cập nhật thông tin cho {len(data)} thiết bị tại {st.session_state.user_name}")

        elif action == "bao_hong":
            st.session_state.requests = pd.concat([st.session_state.requests, data], ignore_index=True)
            luu_nhat_ky("Báo hỏng", f"Đơn vị {st.session_state.user_name} báo hỏng {len(data)} thiết bị")
            
        elif action == "duyet_hong":
            st.session_state.requests.loc[data, 'Trạng_Thái'] = "Đã bù hàng"
            st.session_state.requests.loc[data, 'Thời_Gian_Bù'] = now_s
            luu_nhat_ky("Duyệt bảo hành", f"Admin đã duyệt bù hàng cho {len(data)} yêu cầu")
            
        save_all()
        st.success("Đã xử lý và lưu nhật ký!")
        st.rerun()

# --- 5. ĐĂNG NHẬP ---
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if not st.session_state.logged_in:
    st.markdown("<h1 style='text-align:center; color:#1E3A8A;'>QLVT PC TÂY NINH</h1>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1,1.5,1])
    with c2:
        u = st.selectbox("Tài khoản", ["admin"] + DANH_SACH_14_DOI)
        p = st.text_input("Mật khẩu", type="password")
        if st.button("🔓 Đăng nhập"):
            if p == USER_DB.get(u):
                st.session_state.logged_in = True
                st.session_state.user_role = "admin" if u == "admin" else "doi"
                st.session_state.user_name = u
                st.rerun()
            else:
                st.error("Mật khẩu sai!")
    st.stop()

# --- 6. SIDEBAR ---
# 1. Hiển thị thông tin người dùng và nút Đăng xuất (Phần bị mất)
st.sidebar.write(f"👤 Đang dùng: **{st.session_state.user_name}**")
if st.sidebar.button("Đăng xuất"):
    st.session_state.logged_in = False
    st.rerun()

st.sidebar.markdown("---") # Đường kẻ ngang phân cách cho đẹp

# 2. Menu chức năng (Đã cập nhật thêm mục Hoàn trả)
if st.session_state.user_role == "admin":
    menu = st.sidebar.radio("CÔNG TY", [
        "📊 Giám sát & Dashboard", 
        "📂 Quản lý Văn bản", 
        "📥 Nhập Kho", 
        "🚚 Cấp Phát", 
        "🚨 Duyệt Báo Hỏng", 
        "🔄 Kho Bảo Hành/Hoàn Trả",
        "📜 Nhật ký Hoạt động"  # <--- BỔ SUNG DÒNG NÀY
    ])
else:
    menu = st.sidebar.radio("ĐỘI QLĐ", ["🛠️ Hiện trường (Seri)", "🚨 Báo Hỏng", "📦 Hoàn Trả/Bảo Hành"])
# --- 7. CHI TIẾT CHỨC NĂNG ---

if menu == "📊 Giám sát & Dashboard":
    st.header("Dashboard Giám Sát Lưới")
    df = st.session_state.inventory.copy()
    if not df.empty:
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(px.pie(df, names='Trạng_Thái_Luoi', title="Trạng thái Lưới"), use_container_width=True)
        with c2:
            df_chart = df.groupby(['Vị_Trí_Kho', 'Loại_VT']).size().reset_index(name='SL')
            st.plotly_chart(px.bar(df_chart, x='Vị_Trí_Kho', y='SL', color='Loại_VT', title="Phân bổ vật tư theo loại", barmode='group'), use_container_width=True)
        
        st.markdown("---")
        df.insert(0, "Xóa", False)
        edited = st.data_editor(df, use_container_width=True)
        to_del = edited[edited["Xóa"] == True]["ID_He_Thong"].tolist()
        if to_del and st.button("🗑️ Xóa vĩnh viễn dòng chọn"):
            confirm_dialog("xoa", to_del)
    else:
        st.info("Kho đang trống.")

elif menu == "📥 Nhập Kho":
    st.header("Nhập Vật Tư Mới")
    t1, t2 = st.tabs(["✍️ Nhập tay", "📁 Excel Nhập"])
    
    # --- TAB 1: NHẬP TAY (ĐÃ SỬA LỖI LIST NHÀ CC) ---
    with t1:
        # 1. Đưa Loại VT ra ngoài form để App cập nhật danh sách Nhà CC ngay lập tức
        lvt = st.selectbox("Chọn Loại Vật Tư", list(DANM_MUC_NCC.keys()))
        
        # 2. Form nhập liệu (Chứa các thông tin còn lại)
        with st.form("f_nhap"):
            # Danh sách Nhà CC sẽ thay đổi dựa theo lvt bên trên
            ncc = st.selectbox("Nhà Cung Cấp", DANM_MUC_NCC[lvt])
            
            c1, c2 = st.columns(2)
            with c1:
                ng = st.selectbox("Nguồn nhập", NGUON_NHAP_NGOAI)
                kh = st.selectbox("Nhập vào kho", CO_SO)
            with c2:
                mod = st.text_input("Model/Mã thiết bị")
                sl = st.number_input("Số lượng", min_value=1, step=1)
                
            if st.form_submit_button("🚀 Gửi xác nhận"):
                now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                new_rows = []
                for _ in range(int(sl)):
                    new_rows.append({
                        'ID_He_Thong': f"TN-{uuid.uuid4().hex[:8].upper()}", 
                        'Năm_SX': NAM_HIEN_TAI, 'Loại_VT': lvt, 'Mã_TB': mod, 'Số_Seri': 'Chưa nhập', 
                        'Nhà_CC': ncc, 'Nguồn_Nhap': ng, 'Vị_Trí_Kho': kh, 'Trạng_Thái_Luoi': 'Dưới kho', 
                        'Mục_Đích': 'Dự phòng tại kho', 'Chi_Tiết_Vị_Trí': '---',
                        'Thoi_Gian_Tao': now, 'Thoi_Gian_Cap_Phat': '---'
                    })
                confirm_dialog("nhap", pd.DataFrame(new_rows))
    with t2:
        mau_nhap = pd.DataFrame(columns=['Số_Lượng', 'Năm_SX', 'Loại_VT', 'Mã_TB', 'Nhà_CC', 'Nguồn_Nhap'])
        mau_nhap.loc[0] = [10, 2025, "Công tơ", "VSE11", "Vinasino", "EVNSPC"]
        st.download_button("📥 Tải file mẫu Nhập (.xlsx)", get_sample_excel(mau_nhap), "Mau_Nhap_Kho.xlsx")
        
        f = st.file_uploader("Nạp Excel Nhập", type=["xlsx"])
        if f and st.button("🚀 Nạp Excel"):
            df_ex = pd.read_excel(f)
            now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            ex_data = []
            for _, r in df_ex.iterrows():
                for i in range(int(r['Số_Lượng'])):
                    ex_data.append({
                        'ID_He_Thong': f"TN-EX-{uuid.uuid4().hex[:6].upper()}-{i}", 
                        'Năm_SX': r['Năm_SX'], 'Loại_VT': str(r['Loại_VT']), 'Mã_TB': str(r['Mã_TB']), 
                        'Số_Seri': 'Chưa nhập', 'Nhà_CC': r['Nhà_CC'], 'Nguồn_Nhap': r['Nguồn_Nhap'], 
                        'Vị_Trí_Kho': CO_SO[0], 'Trạng_Thái_Luoi': 'Dưới kho', 
                        'Mục_Đích': 'Dự phòng tại kho', 'Chi_Tiết_Vị_Trí': '---',
                        'Thoi_Gian_Tao': now, 'Thoi_Gian_Cap_Phat': '---'
                    })
            confirm_dialog("nhap", pd.DataFrame(ex_data))

elif menu == "🚚 Cấp Phát":
    st.header("Cấp Phát Về Đội")
    t1, t2 = st.tabs(["✍️ Cấp tay", "📁 Excel Cấp"])
    with t1:
        tu_k = st.selectbox("Từ kho", CO_SO)
        lvt_c = st.selectbox("Loại VT", list(DANM_MUC_NCC.keys()))
        models = st.session_state.inventory[(st.session_state.inventory['Vị_Trí_Kho'] == tu_k) & (st.session_state.inventory['Loại_VT'] == lvt_c)]['Mã_TB'].unique()
        with st.form("f_cap"):
            m_c = st.selectbox("Model", models if len(models)>0 else ["Trống"])
            den = st.selectbox("Đến Đội", DANH_SACH_14_DOI)
            sl_c = st.number_input("SL", min_value=1, step=1)
            if st.form_submit_button("🚀 Cấp"):
                ton_kho = len(st.session_state.inventory[(st.session_state.inventory['Vị_Trí_Kho'] == tu_k) & (st.session_state.inventory['Mã_TB'] == m_c)])
                if sl_c > ton_kho:
                    st.error(f"Không đủ tồn kho! (Hiện có: {ton_kho})")
                else:
                    confirm_dialog("cap_phat", pd.DataFrame([{'Từ_Kho': tu_k, 'Mã_TB': m_c, 'Số_Lượng': sl_c, 'Đến_Đơn_Vị': den}]))
    with t2:
        mau_cap = pd.DataFrame(columns=['Từ_Kho', 'Mã_TB', 'Số_Lượng', 'Đến_Đơn_Vị'])
        mau_cap.loc[0] = [CO_SO[0], "VSE11", 5, DANH_SACH_14_DOI[0]]
        st.download_button("📥 Tải file mẫu Cấp Phát (.xlsx)", get_sample_excel(mau_cap), "Mau_Cap_Phat.xlsx")
        
        f_c = st.file_uploader("Nạp Excel Cấp", type=["xlsx"])
        if f_c and st.button("🚀 Nạp Excel Cấp"):
            confirm_dialog("cap_phat", pd.read_excel(f_c))

# --- ADMIN: DUYỆT BÁO HỎNG & LỊCH SỬ BÙ HÀNG ---
elif menu == "🚨 Duyệt Báo Hỏng":
    st.header("🚨 Quản lý Duyệt Bù Hàng & Báo Hỏng")
    
    # Chia 2 Tab: Chờ xử lý và Lịch sử
    t1, t2 = st.tabs(["⏳ Yêu cầu Chờ duyệt", "✅ Lịch sử Hàng Đã Bù"])
    
   # --- TAB 1: DUYỆT YÊU CẦU MỚI (ĐÃ SỬA LỖI KHÔNG MẤT DÒNG) ---
    with t1:
        # Lọc các yêu cầu chưa được xử lý
        # Lưu ý: .copy() để không ảnh hưởng dữ liệu gốc khi hiển thị
        req_pending = st.session_state.requests[st.session_state.requests['Trạng_Thái'] != "Đã bù hàng"].copy()
        
        if not req_pending.empty:
            st.info(f"🔔 Có {len(req_pending)} yêu cầu báo hỏng đang chờ xử lý.")
            
            # Thêm cột Duyệt
            req_pending.insert(0, "Duyệt", False)
            
            edited = st.data_editor(
                req_pending, 
                use_container_width=True, 
                disabled=[c for c in req_pending.columns if c != "Duyệt"],
                key="editor_duyet_hong"
            )
            
            # Nút duyệt
            if st.button("✅ Phê duyệt bù hàng ngay"):
                to_app = edited[edited["Duyệt"] == True]
                
                if not to_app.empty:
                    target_indices = to_app.index.tolist()
                    
                    # SỬA DÒNG NÀY:
                    now_str = get_vn_time()
                    
                    st.session_state.requests.loc[target_indices, 'Trạng_Thái'] = "Đã bù hàng"
                
                if not to_app.empty:
                    # Lấy danh sách Index (Vị trí dòng) của các yêu cầu được chọn
                    # Vì req_pending giữ nguyên Index từ bảng gốc, nên ta dùng Index này để cập nhật ngược lại bảng gốc
                    target_indices = to_app.index.tolist()
                    
                    now_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                    
                    # Cập nhật trực tiếp vào Session State
                    st.session_state.requests.loc[target_indices, 'Trạng_Thái'] = "Đã bù hàng"
                    st.session_state.requests.loc[target_indices, 'Thời_Gian_Bù'] = now_str
                    
                    # Ghi nhật ký
                    cnt = len(target_indices)
                    luu_nhat_ky("Duyệt bảo hành", f"Admin đã duyệt bù hàng cho {cnt} thiết bị.")
                    
                    # 1. Lưu xuống Database
                    save_all()
                    
                    # 2. QUAN TRỌNG: TẢI LẠI DỮ LIỆU TỪ SQL ĐỂ MÀN HÌNH CẬP NHẬT NGAY
                    # Dòng này sẽ xóa bộ nhớ đệm cũ và lấy dữ liệu mới nhất (đã lọc bỏ hàng đã duyệt)
                    st.session_state.inventory, st.session_state.requests = load_data()
                    
                    st.success(f"🎉 Đã duyệt xong {cnt} yêu cầu!")
                    st.rerun()
                else:
                    st.warning("Vui lòng tích chọn yêu cầu cần duyệt.")
        else:
            st.success("✅ Tuyệt vời! Không có yêu cầu báo hỏng nào tồn đọng.")

    # --- TAB 2: LỊCH SỬ ĐÃ BÙ (TÍNH NĂNG MỚI BẠN YÊU CẦU) ---
    with t2:
        st.write("🔍 **Danh sách các thiết bị đã được Admin duyệt cấp bù:**")
        
        # Lọc các yêu cầu ĐÃ BÙ
        req_done = st.session_state.requests[st.session_state.requests['Trạng_Thái'] == "Đã bù hàng"].copy()
        
        if not req_done.empty:
            # Sắp xếp mới nhất lên đầu
            # (Giả sử cột ID hoặc index tăng dần theo thời gian)
            req_done = req_done.sort_index(ascending=False)
            
            st.dataframe(
                req_done,
                use_container_width=True,
                column_config={
                    "Thời_Gian_Bù": st.column_config.TextColumn("Ngày được bù", help="Thời điểm Admin duyệt"),
                    "Thời_Gian_Báo": "Ngày báo hỏng",
                    "Đơn_Vị": "Đơn vị nhận",
                    "Tên_Vật_Tư": "Thiết bị",
                },
                hide_index=True
            )
            
            st.download_button(
                "📥 Tải danh sách Đã bù (.xlsx)",
                get_sample_excel(req_done),
                f"Lich_Su_Bu_Hang_{datetime.date.today()}.xlsx"
            )
        else:
            st.info("Chưa có dữ liệu lịch sử bù hàng.")

# --- MENU HIỆN TRƯỜNG & THAY THẾ THU HỒI (NÂNG CẤP) ---
elif menu == "🛠️ Hiện trường (Seri)":
    st.header(f"🛠️ Quản lý Hiện trường: {st.session_state.user_name}")
    
    # Chia làm 3 Tab chuyên biệt
    t1, t2, t3 = st.tabs(["✍️ Cập nhật trạng thái", "🔄 Thay thế & Thu hồi (1 đổi 1)", "⚠️ Kho Thu hồi & Hạn trả"])
    
    # --- TAB 1: CẬP NHẬT TRẠNG THÁI (Code cũ giữ nguyên logic) ---
    with t1:
        st.caption("Dùng để cập nhật thông tin các thiết bị đang giữ (chưa lắp hoặc đã lắp nhưng chưa nhập số liệu).")
        df_dv = st.session_state.inventory[st.session_state.inventory['Vị_Trí_Kho'] == st.session_state.user_name].copy()
        
        if not df_dv.empty:
            loai_chon = st.selectbox("🎯 Lọc loại vật tư", ["Tất cả"] + list(df_dv['Loại_VT'].unique()), key="loc_t1")
            df_display = df_dv if loai_chon == "Tất cả" else df_dv[df_dv['Loại_VT'] == loai_chon]

            edited = st.data_editor(
                df_display[['ID_He_Thong', 'Loại_VT', 'Mã_TB', 'Số_Seri', 'Trạng_Thái_Luoi', 'Mục_Đích', 'Chi_Tiết_Vị_Trí']],
                column_config={
                    "Trạng_Thái_Luoi": st.column_config.SelectboxColumn("TT", options=TRANG_THAI_LIST),
                    "Mục_Đích": st.column_config.SelectboxColumn("Mục đích", options=MUC_DICH_LIST),
                    "Chi_Tiết_Vị_Trí": st.column_config.TextColumn("Ghi chú chi tiết")
                }, 
                disabled=['ID_He_Thong', 'Loại_VT', 'Mã_TB'], 
                use_container_width=True,
                key=f"edit_basic"
            )
            if st.button("💾 Lưu cập nhật"):
                confirm_dialog("hien_truong", edited)
        else:
            st.info("Kho đội đang trống.")

# --- TAB 2: QUẢN LÝ LẮP ĐẶT (CÓ THÊM EXCEL) ---
    with t2:
        # Chia làm 2 chế độ: Nhập tay (Lẻ) và Excel (Hàng loạt)
        mode_t2 = st.radio("Chế độ nhập liệu:", ["✍️ Nhập thủ công (Từng cái)", "📁 Nạp Excel (Hàng loạt)"], horizontal=True, label_visibility="collapsed")
        
        # === PHẦN 1: NHẬP THỦ CÔNG (Code cũ) ===
        if mode_t2 == "✍️ Nhập thủ công (Từng cái)":
            c_mode, c_lvt = st.columns([1.5, 1])
            with c_mode:
                nghiep_vu = st.radio("Nghiệp vụ:", ["Lắp mới (Phát triển KH)", "Thay thế (Định kỳ/Đồng bộ/Sự cố)"], horizontal=True)
                is_thay_the = "Thay thế" in nghiep_vu
            
            with c_lvt:
                df_kho_doi = st.session_state.inventory[
                    (st.session_state.inventory['Vị_Trí_Kho'] == st.session_state.user_name) &
                    (st.session_state.inventory['Trạng_Thái_Luoi'] == "Dưới kho")
                ]
                lvt_list = df_kho_doi['Loại_VT'].unique()
                lvt_chon = st.selectbox("Loại thiết bị lắp", lvt_list if len(lvt_list)>0 else ["(Kho trống)"])
                
            c3, c4 = st.columns(2)
            with c3:
                models = df_kho_doi[df_kho_doi['Loại_VT'] == lvt_chon]['Mã_TB'].unique() if len(lvt_list)>0 else []
                model_chon = st.selectbox("Chọn Model", models if len(models)>0 else ["(Hết hàng)"])
            with c4:
                seris = df_kho_doi[(df_kho_doi['Mã_TB'] == model_chon)]['Số_Seri'].unique() if model_chon != "(Hết hàng)" else []
                seri_chon = st.selectbox("Chọn Số Seri lắp", seris if len(seris)>0 else ["(Hết hàng)"])

            st.write("---")
            with st.form("f_thuc_hien_ht"):
                st.subheader(f"📝 Phiếu thi công: {model_chon} - {seri_chon}")
                c_kh_1, c_kh_2 = st.columns(2)
                kh_name = c_kh_1.text_input("Tên Khách hàng / Mã KH")
                dia_chi = c_kh_2.text_input("Địa chỉ lắp đặt")
                
                ly_do = "Lắp mới P.Triển KH"
                if is_thay_the:
                    st.warning("🔄 Nhập thông tin THU HỒI:")
                    rc1, rc2 = st.columns(2)
                    old_lvt = rc1.selectbox("Loại VT cũ", list(DANM_MUC_NCC.keys()), index=0)
                    old_model = rc2.text_input("Model cũ", placeholder="Vd: VSE11-2018")
                    old_seri = rc1.text_input("Seri cũ (*Bắt buộc)")
                    old_idx = rc2.number_input("Chỉ số chốt", min_value=0.0)
                    ly_do = st.selectbox("Lý do thay", ["Thay định kỳ", "Thay đồng bộ", "Thay hư hỏng", "Khác"])
                
                if st.form_submit_button("🚀 Cập nhật"):
                    if seri_chon == "(Hết hàng)" or not seri_chon:
                        st.error("❌ Chưa chọn thiết bị mới!")
                    elif is_thay_the and not old_seri:
                        st.error("❌ Thiếu Seri cũ!")
                    else:
                        # Logic xử lý (Giống cũ)
                        idx_new = st.session_state.inventory[(st.session_state.inventory['Vị_Trí_Kho'] == st.session_state.user_name) & (st.session_state.inventory['Số_Seri'] == seri_chon)].index
                        st.session_state.inventory.loc[idx_new, 'Trạng_Thái_Luoi'] = "Đã đưa lên lưới"
                        st.session_state.inventory.loc[idx_new, 'Mục_Đích'] = f"KH: {kh_name}"
                        
                        detail = f"Đ/c: {dia_chi}. " + (f"Thay cho: {old_seri} ({ly_do})" if is_thay_the else "Lắp mới PTKH")
                        st.session_state.inventory.loc[idx_new, 'Chi_Tiết_Vị_Trí'] = detail
                        
                        if is_thay_the:
                            deadline = (datetime.datetime.now() + datetime.timedelta(days=7)).strftime("%d/%m/%Y")
                            thu_hoi_row = pd.DataFrame([{
                                'ID_He_Thong': f"TH-{uuid.uuid4().hex[:8].upper()}", 'Năm_SX': "Thu hồi", 'Loại_VT': old_lvt, 'Mã_TB': old_model, 'Số_Seri': old_seri, 'Nhà_CC': "Lưới thu hồi", 'Nguồn_Nhap': f"KH: {kh_name}", 'Vị_Trí_Kho': st.session_state.user_name, 'Trạng_Thái_Luoi': "Vật tư thu hồi", 'Mục_Đích': "Chờ kiểm định", 'Chi_Tiết_Vị_Trí': f"Hạn trả: {deadline} (Chỉ số: {old_idx}). Lý do: {ly_do}", 'Thoi_Gian_Tao': datetime.datetime.now().strftime("%d/%m/%Y %H:%M"), 'Thoi_Gian_Cap_Phat': '---'
                            }])
                            st.session_state.inventory = pd.concat([st.session_state.inventory, thu_hoi_row], ignore_index=True)
                            luu_nhat_ky("Thay thế", f"Lắp {seri_chon}, Thu hồi {old_seri}")
                        else:
                            luu_nhat_ky("Lắp mới", f"Lắp mới {seri_chon} cho {kh_name}")
                        
                        save_all()
                        st.success("✅ Thành công!")
                        st.rerun()

        # === PHẦN 2: NẠP EXCEL (TÍNH NĂNG MỚI) ===
        else:
            st.info("💡 File Excel cần có cột 'Nghiệp_Vụ' (điền 'Lắp mới' hoặc 'Thay thế'). Hệ thống tự động xử lý và tính hạn thu hồi.")
            
            # Tạo file mẫu thông minh
            mau_ht = pd.DataFrame({
                'Nghiệp_Vụ': ['Lắp mới', 'Thay thế'],
                'Seri_Mới_Lắp': ['123456', '789012'],
                'Tên_KH': ['Nguyễn Văn A', 'Lê Thị B'],
                'Địa_Chỉ': ['Số 1 Đường A', 'Số 2 Đường B'],
                'Seri_Cũ_Thu_Hồi': ['', 'OLD-999'],
                'Model_Cũ': ['', 'VSE11-2015'],
                'Chỉ_Số_Chốt': ['', 15430],
                'Lý_Do_Thay': ['', 'Thay định kỳ'],
                'Loại_VT_Cũ': ['', 'Công tơ']
            })
            st.download_button("📥 Tải file mẫu Hiện trường (.xlsx)", get_sample_excel(mau_ht), "Mau_Hien_Truong.xlsx")
            
            f_ht = st.file_uploader("Upload Excel", type=["xlsx"])
            if f_ht and st.button("🚀 Xử lý hàng loạt"):
                try:
                    df_up = pd.read_excel(f_ht)
                    df_up.columns = [c.strip() for c in df_up.columns] # Chuẩn hóa tên cột
                    
                    count_ok = 0
                    errors = []
                    today_str = datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                    deadline_str = (datetime.datetime.now() + datetime.timedelta(days=7)).strftime("%d/%m/%Y")
                    
                    for idx, row in df_up.iterrows():
                        seri_moi = str(row['Seri_Mới_Lắp'])
                        nghiep_vu = str(row['Nghiệp_Vụ']).lower()
                        
                        # 1. Kiểm tra tồn kho cái mới
                        mask_new = (st.session_state.inventory['Vị_Trí_Kho'] == st.session_state.user_name) & \
                                   (st.session_state.inventory['Số_Seri'] == seri_moi) & \
                                   (st.session_state.inventory['Trạng_Thái_Luoi'] == "Dưới kho")
                        found_idx = st.session_state.inventory[mask_new].index
                        
                        if found_idx.empty:
                            errors.append(f"Dòng {idx+2}: Seri mới {seri_moi} không có trong kho Đội hoặc đã lắp.")
                            continue
                        
                        # 2. Xử lý Logic
                        i = found_idx[0]
                        st.session_state.inventory.loc[i, 'Trạng_Thái_Luoi'] = "Đã đưa lên lưới"
                        st.session_state.inventory.loc[i, 'Mục_Đích'] = f"KH: {row['Tên_KH']}"
                        
                        detail_note = f"Đ/c: {row['Địa_Chỉ']}. "
                        
                        # Nếu là Thay thế -> Tạo dòng thu hồi
                        if "thay" in nghiep_vu:
                            seri_cu = str(row['Seri_Cũ_Thu_Hồi'])
                            if not seri_cu or seri_cu == "nan":
                                errors.append(f"Dòng {idx+2}: Nghiệp vụ Thay thế nhưng thiếu Seri cũ.")
                                continue # Bỏ qua dòng lỗi này, không lưu
                                
                            detail_note += f"Thay cho: {seri_cu} ({row.get('Lý_Do_Thay', '')})"
                            
                            # Tạo dòng thu hồi
                            thu_hoi_row = pd.DataFrame([{
                                'ID_He_Thong': f"TH-EX-{uuid.uuid4().hex[:6].upper()}",
                                'Năm_SX': "Thu hồi", 
                                'Loại_VT': str(row.get('Loại_VT_Cũ', 'Công tơ')), 
                                'Mã_TB': str(row.get('Model_Cũ', 'Thu hồi')), 
                                'Số_Seri': seri_cu,
                                'Nhà_CC': "Lưới thu hồi", 
                                'Nguồn_Nhap': f"KH: {row['Tên_KH']}", 
                                'Vị_Trí_Kho': st.session_state.user_name,
                                'Trạng_Thái_Luoi': "Vật tư thu hồi", 
                                'Mục_Đích': "Chờ kiểm định", 
                                'Chi_Tiết_Vị_Trí': f"Hạn trả: {deadline_str} (CS: {row.get('Chỉ_Số_Chốt', 0)}). Lý do: {row.get('Lý_Do_Thay', 'Thay thế')}",
                                'Thoi_Gian_Tao': today_str, 
                                'Thoi_Gian_Cap_Phat': '---'
                            }])
                            st.session_state.inventory = pd.concat([st.session_state.inventory, thu_hoi_row], ignore_index=True)
                        else:
                            detail_note += "Lắp mới (Excel)"
                        
                        # Cập nhật ghi chú cho cái mới
                        st.session_state.inventory.loc[i, 'Chi_Tiết_Vị_Trí'] = detail_note
                        count_ok += 1

                    if count_ok > 0:
                        luu_nhat_ky("Hiện trường (Excel)", f"Đội {st.session_state.user_name} cập nhật hàng loạt {count_ok} thiết bị.")
                        save_all()
                        st.success(f"✅ Đã xử lý thành công {count_ok} dòng!")
                    
                    if errors:
                        st.error(f"⚠️ Có {len(errors)} dòng lỗi không thực hiện được:")
                        st.write(errors)
                        
                except Exception as e:
                    st.error(f"Lỗi file Excel: {e}")

    # --- TAB 3: THEO DÕI HẠN TRẢ (CẢNH BÁO) ---
    with t3:
        st.subheader("⚠️ Danh sách Vật tư thu hồi (Cần trả về kho Công ty)")
        
        # Lọc các vật tư có trạng thái "Vật tư thu hồi" của Đội
        df_thu_hoi = st.session_state.inventory[
            (st.session_state.inventory['Vị_Trí_Kho'] == st.session_state.user_name) &
            (st.session_state.inventory['Trạng_Thái_Luoi'] == "Vật tư thu hồi")
        ].copy()
        
        if not df_thu_hoi.empty:
            # Tính toán số ngày còn lại
            now = datetime.datetime.now()
            
            def check_deadline(note):
                # Trích xuất ngày từ chuỗi "Hạn trả: 28/12/2025 ..."
                try:
                    match = re.search(r"Hạn trả: (\d{2}/\d{2}/\d{4})", str(note))
                    if match:
                        d_str = match.group(1)
                        d_obj = datetime.datetime.strptime(d_str, "%d/%m/%Y")
                        delta = (d_obj - now).days
                        return delta, d_str
                except:
                    return 999, "KXD"
                return 999, "KXD"

            # Tạo danh sách hiển thị đẹp
            display_data = []
            for _, row in df_thu_hoi.iterrows():
                days_left, d_str = check_deadline(row['Chi_Tiết_Vị_Trí'])
                status_icon = "🟢"
                msg = f"Còn {days_left} ngày"
                
                if days_left < 0:
                    status_icon = "🔴"
                    msg = f"QUÁ HẠN {-days_left} NGÀY!"
                elif days_left <= 2:
                    status_icon = "🟠"
                    msg = f"Gấp! Còn {days_left} ngày"
                
                display_data.append({
                    "Cảnh báo": status_icon,
                    "Loại": row['Loại_VT'],
                    "Seri Thu Hồi": row['Số_Seri'],
                    "Hạn chót": d_str,
                    "Tình trạng": msg,
                    "Ghi chú": row['Chi_Tiết_Vị_Trí']
                })
            
            st.dataframe(pd.DataFrame(display_data), use_container_width=True)
            st.caption("🔴: Quá hạn (Cần trả ngay) | 🟠: Sắp hết hạn (<= 2 ngày) | 🟢: Còn hạn")
            
            # Nút tạo lệnh trả nhanh
            if st.button("📦 Tạo lệnh Hoàn trả về kho Công ty ngay"):
                # Chuyển hướng người dùng sang Menu Hoàn trả (Gợi ý)
                st.info("Vui lòng qua menu '📦 Hoàn Trả/Bảo Hành' để lập phiếu xuất kho trả các vật tư này.")
        else:
            st.success("✅ Không có vật tư thu hồi nào tồn đọng.")

# --- ĐỘI: BÁO HỎNG & THEO DÕI (CÓ THÊM BẢNG THEO DÕI) ---
elif menu == "🚨 Báo Hỏng":
    st.header("🚨 Báo Hỏng & Theo Dõi Bù Hàng")
    
    # Chia 3 Tab: Nhập tay, Excel và Theo dõi
    t1, t2, t3 = st.tabs(["✍️ Báo hỏng (Mới)", "📁 Nạp Excel", "👀 Theo dõi Trạng thái"])
    
    # --- TAB 1: BÁO HỎNG THỦ CÔNG ---
    with t1:
        with st.form("f_h"):
            c1, c2 = st.columns(2)
            lvt = c1.selectbox("Loại VT", list(DANM_MUC_NCC.keys()))
            ncc = c2.selectbox("Nhà Cung Cấp", DANM_MUC_NCC[lvt])
            
            c3, c4 = st.columns(2)
            tvt = c3.text_input("Tên Vật Tư (Vd: Công tơ xoay chiều...)")
            cl = c4.text_input("Model/Chủng loại")
            
            sl = st.number_input("Số Lượng", min_value=1, step=1)
            ly_do = st.text_area("Lý do hỏng/Mô tả tình trạng")
            
            if st.form_submit_button("🚀 Gửi báo hỏng"):
                # SỬA DÒNG NÀY:
                now = get_vn_time()
                
                new_h = pd.DataFrame([{
                    'Thời_Gian_Báo': now,
                    'Đơn_Vị': st.session_state.user_name, 
                    'Loại_VT': lvt, 
                    'Tên_Vật_Tư': tvt, 
                    'Nhà_CC': ncc, 
                    'Chủng_Loại': cl, 
                    'Số_Lượng': sl, 
                    'Lý_Do': ly_do if ly_do else 'Hỏng hiện trường', 
                    'Trạng_Thái': 'Chờ xử lý', # Mặc định là chờ
                    'Thời_Gian_Bù': '---'
                }])
                confirm_dialog("bao_hong", new_h)

    # --- TAB 2: NẠP EXCEL ---
    with t2:
        st.info("💡 Tải file mẫu, điền thông tin và nạp lại để báo hỏng hàng loạt.")
        # Tạo file mẫu
        mau_bao_hong = pd.DataFrame({
            'Loại_VT': ['Công tơ', 'Modem'],
            'Tên_Vật_Tư': ['Công tơ 1 pha', 'Modem 3G'],
            'Nhà_CC': ['Vinasino', 'Nam Thanh'],
            'Chủng_Loại': ['VSE11', 'NT-Router'],
            'Số_Lượng': [2, 1],
            'Lý_Do': ['Cháy hỏng', 'Mất tín hiệu']
        })
        st.download_button("📥 Tải file mẫu Báo hỏng", get_sample_excel(mau_bao_hong), "Mau_Bao_Hong.xlsx")
        
        f_h = st.file_uploader("Nạp Excel Báo hỏng", type=["xlsx"])
        if f_h and st.button("🚀 Gửi Excel"):
            try:
                df_bh = pd.read_excel(f_h)
                # Tự động điền các cột hệ thống
                df_bh['Thời_Gian_Báo'] = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                df_bh['Đơn_Vị'] = st.session_state.user_name
                df_bh['Trạng_Thái'] = 'Chờ xử lý'
                df_bh['Thời_Gian_Bù'] = '---'
                
                confirm_dialog("bao_hong", df_bh)
            except Exception as e:
                st.error(f"Lỗi file Excel: {e}")

    # --- TAB 3: THEO DÕI TRẠNG THÁI (TÍNH NĂNG MỚI BẠN YÊU CẦU) ---
    with t3:
        st.subheader(f"📋 Danh sách yêu cầu của: {st.session_state.user_name}")
        
        # Lọc ra các yêu cầu CỦA CHÍNH ĐỘI ĐÓ
        my_reqs = st.session_state.requests[st.session_state.requests['Đơn_Vị'] == st.session_state.user_name].copy()
        
        if not my_reqs.empty:
            # Sắp xếp mới nhất lên đầu
            my_reqs = my_reqs.sort_index(ascending=False)
            
            # Tô màu trạng thái cho dễ nhìn
            def highlight_status(val):
                color = '#d4edda' if val == 'Đã bù hàng' else '#fff3cd' # Xanh lá nhẹ nếu xong, Vàng nhẹ nếu chờ
                return f'background-color: {color}'

            st.dataframe(
                my_reqs[['Thời_Gian_Báo', 'Tên_Vật_Tư', 'Số_Lượng', 'Lý_Do', 'Trạng_Thái', 'Thời_Gian_Bù']]
                .style.applymap(highlight_status, subset=['Trạng_Thái']),
                use_container_width=True,
                column_config={
                    "Trạng_Thái": st.column_config.TextColumn("Trạng thái", help="Xem đã được duyệt chưa"),
                    "Thời_Gian_Bù": st.column_config.TextColumn("Ngày được cấp bù")
                }
            )
            
            # Thống kê nhanh
            da_bu = len(my_reqs[my_reqs['Trạng_Thái'] == 'Đã bù hàng'])
            dang_cho = len(my_reqs) - da_bu
            st.caption(f"📊 Tổng kết: **{da_bu}** đã xong | **{dang_cho}** đang chờ.")
            
        else:
            st.info("Bạn chưa gửi yêu cầu báo hỏng nào.")
# --- ĐỘI: GỬI YÊU CẦU TRẢ (Bổ sung ghi nhật ký) ---
elif menu == "📦 Hoàn Trả/Bảo Hành":
    st.header(f"📦 Yêu cầu Hoàn trả / Bảo hành: {st.session_state.user_name}")
    
    # Chia tab
    t1, t2 = st.tabs(["✍️ Chọn từ danh sách", "📁 Nạp từ Excel"])
    
    # --- TAB 1: CHỌN TAY ---
    with t1:
        df_dv = st.session_state.inventory[st.session_state.inventory['Vị_Trí_Kho'] == st.session_state.user_name].copy()
        if not df_dv.empty:
            df_dv.insert(0, "Chọn", False)
            cols_show = ['Chọn', 'ID_He_Thong', 'Loại_VT', 'Mã_TB', 'Số_Seri', 'Trạng_Thái_Luoi']
            edited_return = st.data_editor(
                df_dv[cols_show],
                column_config={
                    "Chọn": st.column_config.CheckboxColumn("Trả về?", default=False),
                    "Mã_TB": st.column_config.TextColumn("Model/Mã TB"),
                },
                use_container_width=True,
                disabled=['ID_He_Thong', 'Loại_VT', 'Mã_TB', 'Số_Seri', 'Trạng_Thái_Luoi'],
                key="return_editor_manual"
            )
            c1, c2 = st.columns(2)
            with c1:
                ly_do = st.selectbox("📌 Lý do hoàn trả", ["Thiết bị hỏng/Lỗi", "Không phù hợp nhu cầu", "Thừa vật tư", "Bảo hành định kỳ", "Thu hồi về kho"], key="ld_1")
            with c2:
                kho_den = st.selectbox("🚚 Chuyển về kho", CO_SO, key="kd_1")

            if st.button("🚀 Gửi yêu cầu (Chọn tay)"):
                selected_ids = edited_return[edited_return["Chọn"] == True]["ID_He_Thong"].tolist()
                if selected_ids:
                    idx = st.session_state.inventory[st.session_state.inventory['ID_He_Thong'].isin(selected_ids)].index
                    st.session_state.inventory.loc[idx, 'Vị_Trí_Kho'] = f"ĐANG CHUYỂN: {kho_den}"
                    st.session_state.inventory.loc[idx, 'Chi_Tiết_Vị_Trí'] = f"Lý do: {ly_do} (Từ: {st.session_state.user_name})"
                    
                    # --- BỔ SUNG GHI NHẬT KÝ CHO ĐỘI ---
                    sl = len(selected_ids)
                    luu_nhat_ky("Hoàn trả/Bảo hành", f"Đội {st.session_state.user_name} gửi trả {sl} thiết bị về {kho_den}. Lý do: {ly_do}")
                    
                    save_all()
                    st.success(f"Đã gửi {len(selected_ids)} thiết bị!")
                    st.rerun()
                else:
                    st.warning("Chưa chọn thiết bị nào!")
        else:
            st.info("Kho trống.")

    # --- TAB 2: NẠP TỪ EXCEL ---
    with t2:
        st.write("Dùng khi cần trả hàng loạt thiết bị.")
        # ... (Phần nút tải mẫu giữ nguyên, chỉ sửa phần xử lý bên dưới) ...
        f_tra = st.file_uploader("Upload Excel Hoàn trả", type=["xlsx"])
        
        if f_tra and st.button("🚀 Xử lý file Excel"):
            try:
                df_upload = pd.read_excel(f_tra)
                df_upload.columns = [c.strip() for c in df_upload.columns]
                
                required_cols = ['Mã_TB', 'Số_Seri', 'Chuyển_Về_Kho']
                if not all(col in df_upload.columns for col in required_cols):
                    st.error(f"File thiếu cột: {required_cols}")
                else:
                    count_ok = 0
                    for index, row in df_upload.iterrows():
                        mask = (
                            (st.session_state.inventory['Vị_Trí_Kho'] == st.session_state.user_name) & 
                            (st.session_state.inventory['Mã_TB'] == str(row['Mã_TB'])) & 
                            (st.session_state.inventory['Số_Seri'] == str(row['Số_Seri']))
                        )
                        found_idx = st.session_state.inventory[mask].index
                        if not found_idx.empty:
                            i = found_idx[0]
                            st.session_state.inventory.loc[i, 'Vị_Trí_Kho'] = f"ĐANG CHUYỂN: {row['Chuyển_Về_Kho']}"
                            st.session_state.inventory.loc[i, 'Chi_Tiết_Vị_Trí'] = f"Excel: {row.get('Lý_Do', 'Excel Import')} (Từ: {st.session_state.user_name})"
                            count_ok += 1
                    
                    if count_ok > 0:
                        # --- BỔ SUNG GHI NHẬT KÝ CHO ĐỘI (EXCEL) ---
                        luu_nhat_ky("Hoàn trả (Excel)", f"Đội {st.session_state.user_name} gửi trả {count_ok} thiết bị qua Excel.")
                        
                        save_all()
                        st.success(f"✅ Đã gửi thành công {count_ok} thiết bị!")
                        st.rerun()
                    else:
                        st.warning("Không tìm thấy thiết bị nào khớp trong kho của bạn.")
            except Exception as e:
                st.error(f"Lỗi: {e}")
# --- CHỨC NĂNG DÀNH CHO ADMIN: NHẬN HÀNG TRẢ VỀ ---
# --- 1. MENU DUYỆT NHẬP KHO (Dành cho Admin duyệt hàng Đội trả về) ---
elif menu == "🔄 Kho Bảo Hành/Hoàn Trả":
    st.header("🔄 Duyệt Nhập Kho (Hoàn trả / Bảo hành)")
    
    # Lọc các vật tư có trạng thái kho là "ĐANG CHUYỂN"
    mask_pending = st.session_state.inventory['Vị_Trí_Kho'].str.contains("ĐANG CHUYỂN", na=False)
    df_return = st.session_state.inventory[mask_pending].copy()
    
    if not df_return.empty:
        st.info(f"🔔 Hiện có {len(df_return)} thiết bị các Đội đang gửi trả về.")
        
        # Thêm cột xác nhận
        df_return.insert(0, "Xác nhận", False)
        
        # Cấu hình bảng hiển thị
        cols_admin = ['Xác nhận', 'ID_He_Thong', 'Loại_VT', 'Mã_TB', 'Số_Seri', 'Vị_Trí_Kho', 'Chi_Tiết_Vị_Trí']
        edited_admin = st.data_editor(
            df_return[cols_admin],
            column_config={
                "Xác nhận": st.column_config.CheckboxColumn("Đã nhận hàng?", default=False),
                "Vị_Trí_Kho": st.column_config.TextColumn("Trạng thái"),
                "Chi_Tiết_Vị_Trí": st.column_config.TextColumn("Lý do & Nguồn gốc", width="medium"),
            },
            use_container_width=True,
            disabled=[c for c in cols_admin if c != "Xác nhận"],
            key="admin_return_only"
        )
        
        # Nút xử lý
        if st.button("✅ Xác nhận Nhập kho"):
            to_confirm = edited_admin[edited_admin["Xác nhận"] == True]
            
            if not to_confirm.empty:
                for _, row in to_confirm.iterrows():
                    target_id = row['ID_He_Thong']
                    current_status = row['Vị_Trí_Kho'] 
                    
                    # Lấy tên kho đích thực sự
                    real_warehouse = current_status.split(": ")[-1] if ": " in current_status else CO_SO[0]
                    
                    # Cập nhật Inventory
                    idx = st.session_state.inventory[st.session_state.inventory['ID_He_Thong'] == target_id].index
                    st.session_state.inventory.loc[idx, 'Vị_Trí_Kho'] = real_warehouse
                    
                    # Cập nhật trạng thái
                    note = str(row['Chi_Tiết_Vị_Trí']).lower()
                    if "hỏng" in note or "lỗi" in note or "bảo hành" in note:
                        st.session_state.inventory.loc[idx, 'Trạng_Thái_Luoi'] = "Chờ bảo hành/Sửa chữa"
                        st.session_state.inventory.loc[idx, 'Mục_Đích'] = "Hàng lỗi chờ xử lý"
                    else:
                        st.session_state.inventory.loc[idx, 'Trạng_Thái_Luoi'] = "Dưới kho"
                        st.session_state.inventory.loc[idx, 'Mục_Đích'] = "Thu hồi về kho"

                    # Ghi nhật ký
                    luu_nhat_ky("Nhập kho Hoàn trả", f"Đã nhận {row['Mã_TB']} ({row['Số_Seri']}) về {real_warehouse}. Note: {note}")

                save_all()
                st.success(f"🎉 Đã nhập kho thành công {len(to_confirm)} thiết bị!")
                st.rerun()
            else:
                st.warning("Vui lòng tích chọn thiết bị cần nhập.")
    else:
        st.success("✅ Không có yêu cầu hoàn trả nào đang chờ.")

# --- 2. MENU NHẬT KÝ HỆ THỐNG (Xem lịch sử truy vết) ---
elif menu == "📜 Nhật ký Hệ thống":
    st.header("📜 Tra cứu Nhật ký & Lịch sử Điều chuyển")
    
    # Bộ lọc
    c1, c2 = st.columns(2)
    ngay_xem = c1.date_input("Xem từ ngày", datetime.date.today())
    loai_hd = c2.selectbox("Lọc theo hành động", ["Tất cả", "Nhập kho Hoàn trả", "Điều chuyển/Cấp phát", "Báo hỏng", "Xóa dữ liệu"])
    
    st.write("---")
    
    engine = get_engine()
    try:
        sql_query = "SELECT * FROM nhat_ky_he_thong ORDER BY id DESC LIMIT 500"
        df_log = pd.read_sql(sql_query, engine)
        
        if not df_log.empty:
            if loai_hd != "Tất cả":
                df_log = df_log[df_log['hanh_dong'].str.contains(loai_hd, case=False, na=False)]
            
            st.dataframe(
                df_log, 
                use_container_width=True, 
                hide_index=True,
                column_config={
                    "thoi_gian": "Thời gian",
                    "nguoi_thuc_hien": "Người thực hiện",
                    "hanh_dong": "Hành động",
                    "noi_dung_chi_tiet": "Chi tiết nội dung"
                }
            )
            
            st.download_button(
                "📥 Tải Nhật ký về Excel",
                get_sample_excel(df_log),
                f"Nhat_Ky_{ngay_xem}.xlsx"
            )
        else:
            st.info("Chưa có dữ liệu nhật ký nào.")
            
    except Exception as e:
        st.error(f"Lỗi kết nối bảng nhật ký: {e}")

# --- MENU QUẢN LÝ VĂN BẢN (CHẾ ĐỘ DÒ LỖI DEBUG) ---
elif menu == "📂 Quản lý Văn bản":
    st.header("📂 Kho Văn Bản & Phân Bổ")

# --- 1. HÀM ĐỌC PDF "SIÊU MẠNH" (CHẤP NHẬN MỌI ĐỊNH DẠNG) ---
    def trich_xuat_thong_tin_pdf(uploaded_file):
        try:
            reader = PdfReader(uploaded_file)
            text = ""
            # Đọc 2 trang đầu (đề phòng số văn bản bị đẩy sang trang 2)
            for i in range(min(2, len(reader.pages))):
                text += reader.pages[i].extract_text() + "\n"
            
            # --- DEBUG: In ra console của server để kiểm tra nếu cần ---
            # print(text) 
            
            info = {"so": "", "ngay": None, "noi_dung": ""}
            
            # 1. TÌM SỐ VĂN BẢN (Cải tiến)
            # Logic: Tìm chữ "Số", chấp nhận có hoặc không dấu ":", chấp nhận khoảng trắng lung tung
            # Ví dụ bắt được hết: "Số: 5291", "Số 5291", "Số :5291"
            match_so = re.search(r"Số\s*[:.]?\s*([0-9]+/[A-Z0-9\-\.]+)", text, re.IGNORECASE)
            if match_so: 
                info["so"] = match_so.group(1).strip()
            
            # 2. TÌM NGÀY THÁNG (Cải tiến mạnh)
            # Logic: Chấp nhận mọi ký tự ngăn cách giữa chữ "ngày" và số (dấu chấm, phẩy, khoảng trắng...)
            match_ngay = re.search(r"ngày\s*[\W_]*\s*(\d{1,2})\s*[\W_]*\s*tháng\s*[\W_]*\s*(\d{1,2})\s*[\W_]*\s*năm\s*[\W_]*\s*(\d{4})", text, re.IGNORECASE)
            if match_ngay:
                d, m, y = map(int, match_ngay.groups())
                info["ngay"] = datetime.date(y, m, d)
                
            # 3. TÌM NỘI DUNG (Cải tiến)
            # Logic: Làm sạch văn bản trước khi tìm để tránh bị xuống dòng cắt ngang
            text_clean = re.sub(r'\n+', ' ', text) # Biến xuống dòng thành khoảng trắng
            match_nd = re.search(r"(V/v\s+[\s\S]+?)(?=\s*(?:Kính gửi|Nơi nhận|Tây Ninh,|CỘNG HÒA))", text_clean, re.IGNORECASE)
            if match_nd:
                raw = match_nd.group(1)
                info["noi_dung"] = re.sub(r'\s+', ' ', raw).strip()
                
            return info
        except Exception as e:
            st.error(f"Lỗi đọc PDF: {e}")
            return {"so": "", "ngay": None, "noi_dung": ""}
            
    # 2. FORM UPLOAD
    with st.expander("➕ Thêm văn bản mới", expanded=True):
        file_upload = st.file_uploader("Chọn file văn bản (PDF)", type=['pdf'])
        
        auto_so = ""
        auto_ngay = datetime.date.today()
        auto_nd = ""
        
        # Xử lý ngay khi upload
        if file_upload is not None:
            if file_upload.name.endswith('.pdf'):
                data_pdf = trich_xuat_thong_tin_pdf(file_upload)
                
                if data_pdf["so"]: auto_so = data_pdf["so"]
                if data_pdf["ngay"]: auto_ngay = data_pdf["ngay"]
                if data_pdf["noi_dung"]: auto_nd = data_pdf["noi_dung"]
                
                if data_pdf["so"] or data_pdf["noi_dung"]:
                    st.success("✅ Đã tìm thấy thông tin!")
                else:
                    st.warning("⚠️ Không tìm thấy Số hoặc Nội dung. Hãy kiểm tra phần 'Debug' ở trên xem text bị lỗi gì.")

        with st.form("upload_doc"):
            c1, c2 = st.columns([1, 2])
            so_hieu = c1.text_input("Số văn bản", value=auto_so, placeholder="Vd: 5291/PCTN-KD")
            ngay_ky = c1.date_input("Ngày ký", value=auto_ngay)
            loai_vb = c1.selectbox("Loại văn bản", ["Quyết định Phân bổ", "Lệnh Điều chuyển", "Công văn", "Khác"])
            
            doi_lien_quan = c2.multiselect("Phân bổ cho Đội nào? (Ghi chú)", DANH_SACH_14_DOI)
            mo_ta = c2.text_area("Nội dung / Trích yếu", value=auto_nd, height=100)
            
            if st.form_submit_button("💾 Lưu trữ"):
                if not file_upload:
                    st.error("Thiếu file đính kèm!")
                else:
                    engine = get_engine()
                    file_upload.seek(0)
                    file_bytes = file_upload.read()
                    ghi_chu_txt = ", ".join(doi_lien_quan) if doi_lien_quan else ""
                    
                    doc_data = pd.DataFrame([{
                        'id': str(uuid.uuid4()),
                        'loai_vb': loai_vb,
                        'so_hieu': so_hieu,
                        'ngay_ky': ngay_ky.strftime("%d/%m/%Y"),
                        'mo_ta': mo_ta,
                        'ghi_chu': ghi_chu_txt,
                        'file_data': file_bytes,
                        'file_name': file_upload.name,
                        'nguoi_upload': st.session_state.user_name,
                        'thoi_gian_up': get_vn_time() 
                    }])
                    
                    with engine.begin() as conn:
                        doc_data.to_sql('documents', conn, if_exists='append', index=False)
                    st.success("Lưu thành công!")
                    st.rerun()

    # 3. DANH SÁCH VĂN BẢN (GIỮ NGUYÊN)
    st.write("---")
    st.subheader("🗃 Danh sách văn bản")
    engine = get_engine()
    
    try:
        query = "SELECT id, so_hieu, ngay_ky, mo_ta, loai_vb, file_name, ghi_chu FROM documents ORDER BY thoi_gian_up DESC LIMIT 20"
        df_docs = pd.read_sql(query, engine)
        
        if not df_docs.empty:
            for i, row in df_docs.iterrows():
                with st.container(border=True):
                    c1, c2, c3 = st.columns([1.5, 4, 1.2])
                    
                    with c1:
                        st.markdown(f"**{row['so_hieu']}**")
                        st.caption(f"📅 {row['ngay_ky']}")
                        st.caption(f"🏷️ {row['loai_vb']}")
                    
                    with c2:
                        st.markdown(f"**V/v:** {row['mo_ta']}")
                        if row['ghi_chu']:
                            st.info(f"👉 **Phân bổ:** {row['ghi_chu']}")
                        else:
                            st.caption("_(Chung / Chưa có ghi chú)_")
                        st.caption(f"File: {row['file_name']}")
                    
                    with c3:
                        btn_dl, btn_del = st.columns(2)
                        with btn_dl:
                            file_q = pd.read_sql(f"SELECT file_data FROM documents WHERE id='{row['id']}'", engine)
                            if not file_q.empty:
                                raw_data = file_q.iloc[0]['file_data']
                                if raw_data:
                                    st.download_button("📥", data=bytes(raw_data), file_name=row['file_name'], mime='application/pdf', key=f"dl_{row['id']}_{i}")
                        
                        with btn_del:
                            if st.button("🗑️", key=f"del_{row['id']}_{i}", type="primary"):
                                with engine.begin() as conn:
                                    conn.exec_driver_sql(f"DELETE FROM documents WHERE id = '{row['id']}'")
                                st.toast("Đã xóa!")
                                st.rerun()
        else:
            st.info("Chưa có văn bản nào.")
            
    except Exception as e:
        st.error(f"Lỗi tải danh sách: {e}")
        
# Thêm vào menu của Admin
# --- Nối tiếp vào các elif bên trên ---
elif menu == "📜 Nhật ký Hoạt động":
    st.header("Nhật Ký Truy Vết Hệ Thống")
    
    # Bộ lọc ngày tháng
    d = st.date_input("Chọn ngày xem log", datetime.date.today())
    
    engine = get_engine()
    try:
        # Load dữ liệu từ bảng log
        df_log = pd.read_sql("SELECT * FROM nhat_ky_he_thong ORDER BY id DESC LIMIT 500", engine)
        
        if not df_log.empty:
            # Hiển thị bảng log
            st.dataframe(df_log, use_container_width=True, hide_index=True)
            
            # Nút tải về báo cáo log
            st.download_button(
                "📥 Tải Nhật ký (.xlsx)",
                get_sample_excel(df_log),
                f"Nhat_Ky_He_Thong_{d}.xlsx"
            )
        else:
            st.info("Chưa có nhật ký nào.")
    except Exception as e:
        st.error(f"Lỗi: Chưa tạo bảng 'nhat_ky_he_thong' trên Supabase hoặc lỗi kết nối. ({e})")

















































