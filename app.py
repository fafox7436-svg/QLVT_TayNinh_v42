import streamlit as st
import pandas as pd
import plotly.express as px
import datetime
import io
import os
import uuid
import re
from pypdf import PdfReader

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
        now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
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
    with t1:
        with st.form("f_nhap"):
            lvt = st.selectbox("Loại VT", list(DANM_MUC_NCC.keys()))
            ncc = st.selectbox("Nhà CC", DANM_MUC_NCC[lvt])
            c1, c2 = st.columns(2)
            with c1:
                ng = st.selectbox("Nguồn", NGUON_NHAP_NGOAI)
                kh = st.selectbox("Kho", CO_SO)
            with c2:
                mod = st.text_input("Model")
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

elif menu == "🚨 Duyệt Báo Hỏng":
    st.header("Duyệt Bù Hàng Báo Hỏng")
    req_df = st.session_state.requests.copy()
    if not req_df.empty:
        req_df.insert(0, "Duyệt", False)
        edited = st.data_editor(req_df, use_container_width=True, disabled=[c for c in req_df.columns if c != "Duyệt"])
        to_app = edited[edited["Duyệt"] == True].index.tolist()
        if to_app and st.button("✅ Phê duyệt bù hàng"):
            confirm_dialog("duyet_hong", to_app)
    else:
        st.info("Không có yêu cầu báo hỏng nào.")

elif menu == "🛠️ Hiện trường (Seri)":
    st.header(f"Cập nhật hiện trường: {st.session_state.user_name}")
    df_dv = st.session_state.inventory[st.session_state.inventory['Vị_Trí_Kho'] == st.session_state.user_name].copy()
    
    if not df_dv.empty:
        loai_chon = st.selectbox("🎯 Chọn loại vật tư", ["Tất cả"] + list(df_dv['Loại_VT'].unique()))
        df_display = df_dv if loai_chon == "Tất cả" else df_dv[df_dv['Loại_VT'] == loai_chon]

        t1, t2 = st.tabs(["✍️ Cập nhật tay", "📁 Excel Hiện trường"])
        with t1:
            # DÒNG NÀY PHẢI THỤT LỀ VÀO (Dòng 275)
            edited = st.data_editor(
                df_display[['ID_He_Thong', 'Loại_VT', 'Mã_TB', 'Số_Seri', 'Trạng_Thái_Luoi', 'Mục_Đích', 'Chi_Tiết_Vị_Trí']],
                column_config={
                    "Trạng_Thái_Luoi": st.column_config.SelectboxColumn("TT", options=TRANG_THAI_LIST),
                    # KHÔI PHỤC TÍNH NĂNG CHỌN MỤC ĐÍCH TẠI ĐÂY
                    "Mục_Đích": st.column_config.SelectboxColumn("Mục đích", options=MUC_DICH_LIST),
                    "Chi_Tiết_Vị_Trí": st.column_config.TextColumn("Ghi chú chi tiết")
                }, 
                disabled=['ID_He_Thong', 'Loại_VT', 'Mã_TB'], 
                use_container_width=True,
                key=f"edit_{loai_chon}"
            )
            # Dòng nút bấm cũng phải thụt lề vào để nằm trong 'with t1'
            if st.button("💾 Lưu thay đổi hiện trường"):
                confirm_dialog("hien_truong", edited)
        with t2:
            st.download_button("📥 Tải danh sách vật tư tại Đội", df_dv.to_csv(index=False).encode('utf-8-sig'), "Kho_Doi.csv")
            f_ht = st.file_uploader("Nạp Excel hiện trường", type=["xlsx", "csv"])
            if f_ht and st.button("🚀 Nạp Excel Hiện trường"):
                df_ht = pd.read_excel(f_ht) if f_ht.name.endswith('xlsx') else pd.read_csv(f_ht)
                confirm_dialog("hien_truong", df_ht)
    else:
        st.warning("Kho của Đội hiện đang trống.")

elif menu == "🚨 Báo Hỏng":
    st.header("Báo Hỏng Thiết Bị")
    t1, t2 = st.tabs(["✍️ Báo tay", "📁 Excel Báo hỏng"])
    with t1:
        with st.form("f_h"):
            lvt = st.selectbox("Loại", list(DANM_MUC_NCC.keys()))
            tvt = st.text_input("Tên VT")
            ncc = st.selectbox("Nhà CC", DANM_MUC_NCC[lvt])
            cl = st.text_input("Model/Chủng loại")
            sl = st.number_input("SL", min_value=1, step=1)
            if st.form_submit_button("🚀 Gửi báo hỏng"):
                now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                new_h = pd.DataFrame([{
                    'Thời_Gian_Báo': now, 'Đơn_Vị': st.session_state.user_name, 'Loại_VT': lvt, 
                    'Tên_Vật_Tư': tvt, 'Nhà_CC': ncc, 'Chủng_Loại': cl, 'Số_Lượng': sl, 
                    'Lý_Do': 'Hỏng hiện trường', 'Trạng_Thái': 'Chờ xử lý', 'Thời_Gian_Bù': '---'
                }])
                confirm_dialog("bao_hong", new_h)
    with t2:
        f_h = st.file_uploader("Nạp Excel Báo hỏng", type=["xlsx"])
        if f_h and st.button("🚀 Nạp Excel Báo hỏng"):
            df_bh = pd.read_excel(f_h)
            df_bh['Thời_Gian_Báo'] = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            df_bh['Đơn_Vị'] = st.session_state.user_name
            df_bh['Trạng_Thái'] = 'Chờ xử lý'
            df_bh['Thời_Gian_Bù'] = '---'
            confirm_dialog("bao_hong", df_bh)
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

# --- MENU QUẢN LÝ VĂN BẢN (ĐÃ SỬA LỖI & THÊM NÚT XÓA) ---
elif menu == "📂 Quản lý Văn bản":
    st.header("📂 Kho Văn Bản & Tự Động Trích Xuất")

    # --- HÀM TRÍCH XUẤT PDF THÔNG MINH (Sửa lỗi thiếu số hiệu) ---
    def trich_xuat_thong_tin_pdf(uploaded_file):
        try:
            reader = PdfReader(uploaded_file)
            text = ""
            if len(reader.pages) > 0:
                text = reader.pages[0].extract_text()
            
            info = {"so": "", "ngay": None, "noi_dung": ""}
            
            # 1. Tìm Số văn bản: Cải tiến để bắt được cả số nằm xa chữ "Số:"
            # Tìm chuỗi dạng "5291/..." bất kể có khoảng trắng hay xuống dòng
            match_so = re.search(r"Số:[\s\n._-]*([\d]+/[A-Z0-9\-]+)", text, re.IGNORECASE)
            if match_so:
                info["so"] = match_so.group(1).strip()
            
            # 2. Tìm Ngày tháng
            match_ngay = re.search(r"ngày\s+(\d{1,2})\s+tháng\s+(\d{1,2})\s+năm\s+(\d{4})", text, re.IGNORECASE)
            if match_ngay:
                d, m, y = map(int, match_ngay.groups())
                info["ngay"] = datetime.date(y, m, d)
                
            # 3. Tìm Nội dung (V/v): Cải tiến để lấy hết nội dung dù bị ngắt dòng
            # Lấy từ "V/v" cho đến khi gặp các từ khóa kết thúc như "Kính gửi", "Nơi nhận" hoặc 3 dòng trống
            match_nd = re.search(r"(V/v[\s\S]+?)(?=\n\s*(?:Kính gửi|Nơi nhận|Tây Ninh|CỘNG HÒA)|\n{3,})", text, re.IGNORECASE)
            if match_nd:
                raw = match_nd.group(1)
                # Nối các dòng bị ngắt lại thành 1 câu hoàn chỉnh
                info["noi_dung"] = re.sub(r'\s+', ' ', raw).strip()
                
            return info
        except Exception as e:
            return {"so": "", "ngay": None, "noi_dung": ""}

    # --- FORM UPLOAD ---
    with st.expander("➕ Thêm văn bản mới (Upload PDF để tự điền)", expanded=True):
        file_upload = st.file_uploader("Chọn file văn bản (PDF)", type=['pdf'])
        
        # Biến tạm
        auto_so = ""
        auto_ngay = datetime.date.today()
        auto_nd = ""
        
        if file_upload is not None and file_upload.name.endswith('.pdf'):
            # Đọc thử file
            data_pdf = trich_xuat_thong_tin_pdf(file_upload)
            if data_pdf["so"]: auto_so = data_pdf["so"]
            if data_pdf["ngay"]: auto_ngay = data_pdf["ngay"]
            if data_pdf["noi_dung"]: auto_nd = data_pdf["noi_dung"]
            st.success("✅ Đã đọc xong nội dung file!")

        with st.form("upload_doc"):
            c1, c2 = st.columns([1, 2])
            so_hieu = c1.text_input("Số văn bản", value=auto_so, placeholder="Vd: 5291/PCTN-KD")
            ngay_ky = c1.date_input("Ngày ký", value=auto_ngay)
            loai_vb = c1.selectbox("Loại văn bản", ["Quyết định Phân bổ", "Lệnh Điều chuyển", "Công văn", "Khác"])
            
            mo_ta = c2.text_area("Nội dung / Trích yếu", value=auto_nd, height=100)
            
            if st.form_submit_button("💾 Lưu trữ"):
                if file_upload is None:
                    st.error("Chưa đính kèm file!")
                else:
                    engine = get_engine()
                    file_upload.seek(0) # Reset file để đọc lại từ đầu
                    file_bytes = file_upload.read()
                    
                    doc_data = pd.DataFrame([{
                        'id': str(uuid.uuid4()),
                        'loai_vb': loai_vb,
                        'so_hieu': so_hieu,
                        'ngay_ky': ngay_ky.strftime("%d/%m/%Y"),
                        'mo_ta': mo_ta,
                        'file_data': file_bytes, # Lưu file
                        'file_name': file_upload.name,
                        'nguoi_upload': st.session_state.user_name,
                        'thoi_gian_up': datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                    }])
                    
                    with engine.begin() as conn:
                        doc_data.to_sql('documents', conn, if_exists='append', index=False)
                    st.success("Lưu thành công!")
                    st.rerun()

    # --- DANH SÁCH VĂN BẢN (ĐÃ SỬA LỖI HIỂN THỊ + NÚT TẢI/XÓA) ---
    st.write("---")
    st.subheader("🗃 Danh sách văn bản")
    engine = get_engine()
    
    try:
        # QUAN TRỌNG: KHÔNG SELECT CỘT 'file_data' Ở ĐÂY để tránh lỗi memoryview
        query = "SELECT id, so_hieu, ngay_ky, mo_ta, loai_vb, file_name FROM documents ORDER BY thoi_gian_up DESC LIMIT 20"
        df_docs = pd.read_sql(query, engine)
        
        if not df_docs.empty:
            for i, row in df_docs.iterrows():
                with st.container(border=True):
                    c1, c2, c3 = st.columns([1.5, 4, 1.5])
                    
                    with c1:
                        st.markdown(f"**{row['so_hieu']}**")
                        st.caption(f"📅 {row['ngay_ky']}")
                        st.caption(f"🏷️ {row['loai_vb']}")
                    
                    with c2:
                        st.markdown(f"**V/v:** {row['mo_ta']}")
                        st.caption(f"File: {row['file_name']}")
                    
                    with c3:
                        # 1. NÚT TẢI (Query file riêng cho từng dòng)
                        # Để đảm bảo nút tải hoạt động, ta lấy dữ liệu file NGAY TẠI ĐÂY
                        file_q = pd.read_sql(f"SELECT file_data FROM documents WHERE id='{row['id']}'", engine)
                        if not file_q.empty:
                            file_bytes_dl = file_q.iloc[0]['file_data']
                            st.download_button(
                                label="📥 Tải về",
                                data=file_bytes_dl,
                                file_name=row['file_name'],
                                mime='application/pdf',
                                key=f"dl_{row['id']}",
                                use_container_width=True
                            )
                        
                        # 2. NÚT XÓA (Thêm khoảng cách cho đẹp)
                        st.write("") 
                        if st.button("🗑️ Xóa", key=f"del_{row['id']}", type="primary", use_container_width=True):
                            with engine.begin() as conn:
                                conn.exec_driver_sql(f"DELETE FROM documents WHERE id = '{row['id']}'")
                            st.toast("Đã xóa văn bản!")
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




































