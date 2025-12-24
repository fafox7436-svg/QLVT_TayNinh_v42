import streamlit as st
import pandas as pd
import plotly.express as px
import datetime
import io
import os
import uuid
import re
import pdfplumber
# --- BỘ DANH MỤC CHỦNG LOẠI CÔNG TƠ CHUẨN (PC TÂY NINH) - ĐÃ CẬP NHẬT ---
DM_CHUNG_LOAI_CONG_TO = {
    "Hữu Hồng": [
        # Nhóm HHM cũ
        "T24 - HHM11 (PLC)", "T42 - HHM18", "T50 - HHM-18 GT",
        "41M - HHM-38 (PLC)", "42M - HHM-38GT (PLC)",
        # Nhóm Linkton (Gộp vào theo yêu cầu)
        "T23 - DDS26 (RF)", "T26 - DDS26D", "T21 - DDS26D (RF)",
        "T14 - DDZ1513",
        "43M - DTS27-PDM 044-2015", "44M - DTS27-PDM 045-2015"
    ],
    "Psmart": [ # Đổi từ Star (Điện cơ) thành Psmart
        "T51 - SF10m-10", "T49 - SF80C-10",
        "T40 - SF80C-21", "T28 - SF80C-21",
        "T41 - SF80m-10"
    ],
    "Vinasino": [
        "T03 - VSE11-10 (PLC)", "T04 - VSE11-20 (PLC)", "T33 - VSE1T-10100",
        "T34 - VSE1T-510", "T44 - VSE1T-510B", "T16 - VSE1T-5CT(510) (PLC)",
        "01N - VSE3T-5 (PLC)", "02N - VSE3T-50 (PLC)", "05N - VSE3T-5B (PLC)",
        "T43 - VSE1T-10100B", "47M - VSE3T-10100B"
    ],
    "Gelex/EMIC": [
        "T30 - CE-14", "T31 - CE-14", "T53 - CE-14",
        "T36 - CE-11mGS", "T17 - CE-14mGS", "T10 - CE-18G",
        "45M - ME-41", "46M - ME-42",
        "26M - PB3AABGHT-5", "28M - PB3FAAGHT-5", "29M - PB3KAAGHT-5",
        "09N - TF100m-31", "T48 - TF10m-10", "10N - TF10m-30"
    ],
    "Omnisystem": [
        "T56 - OVE-A002", "T57 - OVE-A003TT10-80",
        "55M - OVE-B002", "56M - OVE-C001MV-63"
    ],
    "Khác": ["Khác"]
}
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
        "📜 Nhật ký Hoạt động",
        "💾 Quản trị Dữ liệu" # <--- BỔ SUNG DÒNG NÀY
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

# --- MENU NHẬP KHO (UPDATE: CHỌN CHỦNG LOẠI CHUẨN) ---
elif menu == "📥 Nhập Kho":
    st.header("Nhập Vật Tư Mới")
    t1, t2 = st.tabs(["✍️ Nhập tay (Chuẩn hóa)", "📁 Excel Nhập"])
    
    # --- TAB 1: NHẬP TAY CHUẨN ---
    with t1:
        # 1. Chọn Loại VT (Công tơ, Modem...)
        lvt = st.selectbox("Chọn Loại Vật Tư", list(DANM_MUC_NCC.keys()))
        
        # 2. Chọn Nhà Cung Cấp
        # Nếu là Công tơ thì dùng danh sách các hãng công tơ, nếu khác thì dùng danh sách cũ
        ds_ncc = list(DM_CHUNG_LOAI_CONG_TO.keys()) if lvt == "Công tơ" else DANM_MUC_NCC.get(lvt, ["Khác"])
        ncc = st.selectbox("Nhà Cung Cấp / Hãng SX", ds_ncc)
        
        with st.form("f_nhap"):
            # 3. Chọn Model/Chủng loại (Tự động nhảy theo NCC)
            if lvt == "Công tơ" and ncc in DM_CHUNG_LOAI_CONG_TO:
                # Nếu là công tơ -> Hiện danh sách chuẩn T24, T42...
                mod_select = st.selectbox("Mã & Tên Chủng Loại", DM_CHUNG_LOAI_CONG_TO[ncc])
                # Tách lấy phần tên sau dấu gạch ngang để lưu cho gọn, hoặc lưu cả chuỗi tùy bạn
                # Ở đây tôi lưu cả chuỗi "T24 - HHM11" để dễ quản lý
                mod = mod_select 
            else:
                # Nếu là vật tư khác -> Nhập tay như cũ
                mod = st.text_input("Model/Mã thiết bị (Nhập tay)", placeholder="Vd: Modem 3G...")

            c1, c2 = st.columns(2)
            with c1:
                ng = st.selectbox("Nguồn nhập", NGUON_NHAP_NGOAI)
                kh = st.selectbox("Nhập vào kho", CO_SO)
            with c2:
                sl = st.number_input("Số lượng", min_value=1, step=1, value=10)
                # Tự động tạo mã lô nhập
                lot_id = f"IMP-{datetime.datetime.now().strftime('%d%m')}"
                st.caption(f"Lô: {lot_id}")
                
            if st.form_submit_button("🚀 Gửi xác nhận"):
                now = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
                new_rows = []
                for i in range(int(sl)):
                    new_rows.append({
                        'ID_He_Thong': f"TN-{uuid.uuid4().hex[:8].upper()}", 
                        'Năm_SX': NAM_HIEN_TAI, 
                        'Loại_VT': lvt, 
                        'Mã_TB': mod, # Lưu giá trị chuẩn (Vd: T24 - HHM11)
                        'Số_Seri': 'Chưa nhập', 
                        'Nhà_CC': ncc, 
                        'Nguồn_Nhap': ng, 
                        'Vị_Trí_Kho': kh, 
                        'Trạng_Thái_Luoi': 'Dưới kho', 
                        'Mục_Đích': 'Dự phòng tại kho', 
                        'Chi_Tiết_Vị_Trí': f'Lô {lot_id}',
                        'Thoi_Gian_Tao': now, 
                        'Thoi_Gian_Cap_Phat': '---'
                    })
                confirm_dialog("nhap", pd.DataFrame(new_rows))

# --- TAB 2: QUẢN LÝ LẮP ĐẶT (FULL CODE: FIX LỖI THỤT DÒNG) ---
    with t2:
        mode_t2 = st.radio("Chế độ nhập liệu:", ["✍️ Nhập thủ công (Từng cái)", "📁 Nạp Excel (Hàng loạt)"], horizontal=True, label_visibility="collapsed")
        
        # === PHẦN 1: NHẬP THỦ CÔNG ===
        if mode_t2 == "✍️ Nhập thủ công (Từng cái)":
            c_mode, c_lvt = st.columns([1.5, 1])
            with c_mode:
                nghiep_vu = st.radio("Nghiệp vụ:", ["Lắp mới (Phát triển KH)", "Thay thế (Định kỳ/Đồng bộ/Sự cố)"], horizontal=True)
                is_thay_the = "Thay thế" in nghiep_vu
            
            with c_lvt:
                # Lọc kho đội
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
                st.subheader(f"📝 Phiếu thi công: {model_chon}")
                
                # --- LOGIC GỢI Ý MÃ CHÌ (ĐÃ CẬP NHẬT) ---
                goi_y_chi = ["VN/N128_LA"] # Mặc định
                model_upper = str(model_chon).upper()
                
                # 1. Hữu Hồng (Gộp Linkton)
                if any(x in model_upper for x in ["HHM", "DDS", "DTS", "DDZ"]):
                    goi_y_chi = ["VN/N309_HHM", "VN/N128_LA", "VN/N139_TN"]
                # 2. Vinasino
                elif "VSE" in model_upper:
                    goi_y_chi = ["VN/N306_VSE1", "VN/N128_LA"]
                # 3. Gelex/EMIC
                elif any(x in model_upper for x in ["CE-", "ME-", "PB", "TF"]):
                    goi_y_chi = ["VN/N52", "VN/N128_LA", "VN/N370"]
                # 4. Omnisystem
                elif "OVE" in model_upper:
                    goi_y_chi = ["VN/N224_3", "VN/N224_4"]
                # 5. Psmart (Star cũ)
                elif "SF" in model_upper:
                    goi_y_chi = ["VN/N370", "VN/N128_LA", "VN/N264_LA"]
                
                goi_y_chi.append("✍️ Nhập tay khác...")
                
                c_chi_1, c_chi_2 = st.columns(2)
                with c_chi_1:
                    chon_chi = st.selectbox("Mã chì kiểm định (Gợi ý)", goi_y_chi)
                with c_chi_2:
                    if chon_chi == "✍️ Nhập tay khác...":
                        ma_chi_final = st.text_input("Nhập mã chì thực tế", placeholder="Vd: VN/N...")
                    else:
                        st.text_input("Mã chì xác nhận", value=chon_chi, disabled=True)
                        ma_chi_final = chon_chi
                
                # --- THÔNG TIN KHÁCH HÀNG ---
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
                    elif not ma_chi_final:
                        st.error("❌ Chưa nhập mã chì!")
                    else:
                        # Logic lưu
                        idx_new = st.session_state.inventory[(st.session_state.inventory['Vị_Trí_Kho'] == st.session_state.user_name) & (st.session_state.inventory['Số_Seri'] == seri_chon)].index
                        st.session_state.inventory.loc[idx_new, 'Trạng_Thái_Luoi'] = "Đã đưa lên lưới"
                        st.session_state.inventory.loc[idx_new, 'Mục_Đích'] = f"KH: {kh_name}"
                        
                        detail = f"Đ/c: {dia_chi}. [Chì: {ma_chi_final}]. " + (f"Thay cho: {old_seri} ({ly_do})" if is_thay_the else "Lắp mới PTKH")
                        st.session_state.inventory.loc[idx_new, 'Chi_Tiết_Vị_Trí'] = detail
                        
                        if is_thay_the:
                            deadline = (datetime.datetime.now() + datetime.timedelta(days=7)).strftime("%d/%m/%Y")
                            thu_hoi_row = pd.DataFrame([{
                                'ID_He_Thong': f"TH-{uuid.uuid4().hex[:8].upper()}", 'Năm_SX': "Thu hồi", 'Loại_VT': old_lvt, 'Mã_TB': old_model, 'Số_Seri': old_seri, 'Nhà_CC': "Lưới thu hồi", 'Nguồn_Nhap': f"KH: {kh_name}", 'Vị_Trí_Kho': st.session_state.user_name, 'Trạng_Thái_Luoi': "Vật tư thu hồi", 'Mục_Đích': "Chờ kiểm định", 'Chi_Tiết_Vị_Trí': f"Hạn trả: {deadline} (Chỉ số: {old_idx}). Lý do: {ly_do}", 'Thoi_Gian_Tao': datetime.datetime.now().strftime("%d/%m/%Y %H:%M"), 'Thoi_Gian_Cap_Phat': '---'
                            }])
                            st.session_state.inventory = pd.concat([st.session_state.inventory, thu_hoi_row], ignore_index=True)
                            luu_nhat_ky("Thay thế", f"Lắp {seri_chon} (Chì: {ma_chi_final}), Thu hồi {old_seri}")
                        else:
                            luu_nhat_ky("Lắp mới", f"Lắp mới {seri_chon} (Chì: {ma_chi_final}) cho {kh_name}")
                        
                        save_all()
                        st.success("✅ Thành công!")
                        st.rerun()

        # === PHẦN 2: NẠP EXCEL (ĐÃ CẬP NHẬT CỘT MÃ CHÌ) ===
        else:
            st.info("💡 File Excel cần có cột 'Nghiệp_Vụ' (điền 'Lắp mới' hoặc 'Thay thế'). Hệ thống tự động xử lý và tính hạn thu hồi.")
            
            # File mẫu cập nhật thêm cột Mã_Chì
            mau_ht = pd.DataFrame({
                'Nghiệp_Vụ': ['Lắp mới', 'Thay thế'],
                'Seri_Mới_Lắp': ['123456', '789012'],
                'Mã_Chì': ['VN/N...', 'VN/N...'], # Cột mới
                'Tên_KH': ['Nguyễn Văn A', 'Lê Thị B'],
                'Địa_Chỉ': ['Số 1 Đường A', 'Số 2 Đường B'],
                'Seri_Cũ_Thu_Hồi': ['', 'OLD-999'],
                'Model_Cũ': ['', 'VSE11-2015'],
                'Chỉ_Số_Chốt': ['', 15430],
                'Lý_Do_Thay': ['', 'Thay định kỳ'],
                'Loại_VT_Cũ': ['', 'Công tơ']
            })
            st.download_button("📥 Tải file mẫu Hiện trường (.xlsx)", get_sample_excel(mau_ht), "Mau_Hien_Truong_v2.xlsx")
            
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
                        ma_chi = str(row.get('Mã_Chì', '')) # Lấy mã chì từ Excel
                        if ma_chi == 'nan': ma_chi = 'Chưa nhập'
                        
                        # 1. Kiểm tra tồn kho
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
                        
                        # Thêm mã chì vào ghi chú
                        detail_note = f"Đ/c: {row['Địa_Chỉ']}. [Chì: {ma_chi}]. "
                        
                        if "thay" in nghiep_vu:
                            seri_cu = str(row['Seri_Cũ_Thu_Hồi'])
                            if not seri_cu or seri_cu == "nan":
                                errors.append(f"Dòng {idx+2}: Nghiệp vụ Thay thế nhưng thiếu Seri cũ.")
                                continue 
                                
                            detail_note += f"Thay cho: {seri_cu} ({row.get('Lý_Do_Thay', '')})"
                            
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
                        
                        st.session_state.inventory.loc[i, 'Chi_Tiết_Vị_Trí'] = detail_note
                        count_ok += 1

                    if count_ok > 0:
                        luu_nhat_ky("Hiện trường (Excel)", f"Đội {st.session_state.user_name} cập nhật hàng loạt {count_ok} thiết bị.")
                        save_all()
                        st.success(f"✅ Đã xử lý thành công {count_ok} dòng!")
                    
                    if errors:
                        st.error(f"⚠️ Có {len(errors)} dòng lỗi:")
                        st.write(errors)
                        
                except Exception as e:
                    st.error(f"Lỗi file Excel: {e}")

# --- MENU CẤP PHÁT (UPDATE: CÓ THÊM PHẦN EXCEL) ---
elif menu == "🚚 Cấp Phát":
    st.header("🚚 Cấp phát Vật tư cho Đội")
    
    t1, t2 = st.tabs(["🚀 Lệnh Cấp Phát / Điều Chuyển", "📂 Lịch sử Cấp phát"])
    
    # --- TAB 1: THỰC HIỆN CẤP PHÁT ---
    with t1:
        # Chọn chế độ nhập liệu
        mode_cp = st.radio("Chế độ cấp phát:", ["✍️ Chọn tay (Trên lưới)", "📁 Nạp Excel (Hàng loạt)"], horizontal=True, label_visibility="collapsed", key="mode_cp_main")
        
        # 1. CHỌN KHO NGUỒN (CHUNG CHO CẢ 2 CHẾ ĐỘ)
        all_kho = st.session_state.inventory['Vị_Trí_Kho'].unique()
        def_ix = 0
        if st.session_state.user_name in all_kho:
            def_ix = list(all_kho).index(st.session_state.user_name)
        elif "PC Tây Ninh - Cơ sở 1" in all_kho:
             def_ix = list(all_kho).index("PC Tây Ninh - Cơ sở 1")

        c_src, c_dst = st.columns(2)
        kho_nguon = c_src.selectbox("Từ Kho (Nguồn):", all_kho, index=def_ix, key="src_kho_cp")
        
        # === CHẾ ĐỘ 1: CHỌN TAY ===
        if mode_cp == "✍️ Chọn tay (Trên lưới)":
            doi_nhan = c_dst.selectbox("Đến Đội (Đích):", DANH_SACH_14_DOI, key="dst_doi_cp")
            st.divider()
            
            # Lọc vật tư khả dụng
            df_avail = st.session_state.inventory[
                (st.session_state.inventory['Vị_Trí_Kho'] == kho_nguon) & 
                (st.session_state.inventory['Trạng_Thái_Luoi'] == "Dưới kho")
            ]
            
            if not df_avail.empty:
                col_f1, col_f2 = st.columns(2)
                list_lvt = df_avail['Loại_VT'].unique()
                filter_lvt = col_f1.selectbox("Lọc Loại VT:", ["Tất cả"] + list(list_lvt), key="fil_lvt_cp")
                
                df_view = df_avail if filter_lvt == "Tất cả" else df_avail[df_avail['Loại_VT'] == filter_lvt]
                
                st.info(f"💡 Kho '{kho_nguon}' có {len(df_view)} thiết bị sẵn sàng cấp.")
                
                with st.form("f_cap_phat_manual"):
                    # Chọn nhiều dòng
                    df_view.insert(0, "Chọn", False)
                    edited_cp = st.data_editor(
                        df_view[['Chọn', 'Loại_VT', 'Mã_TB', 'Số_Seri', 'Năm_SX']],
                        column_config={"Chọn": st.column_config.CheckboxColumn("Cấp?", default=False)},
                        use_container_width=True,
                        key="editor_cp_manual"
                    )
                    
                    ghi_chu_cap = st.text_input("Ghi chú cấp phát (Số Phiếu/Lệnh):")
                    
                    if st.form_submit_button("🚀 Xác nhận Cấp phát"):
                        selected_indices = edited_cp[edited_cp["Chọn"] == True].index.tolist()
                        
                        if not selected_indices:
                            st.warning("⚠️ Chưa chọn thiết bị nào!")
                        else:
                            now_str = get_vn_time()
                            st.session_state.inventory.loc[selected_indices, 'Vị_Trí_Kho'] = doi_nhan
                            st.session_state.inventory.loc[selected_indices, 'Thoi_Gian_Cap_Phat'] = now_str
                            st.session_state.inventory.loc[selected_indices, 'Chi_Tiết_Vị_Trí'] = f"Nhận từ {kho_nguon}. {ghi_chu_cap}"
                            
                            cnt = len(selected_indices)
                            luu_nhat_ky("Cấp phát", f"Điều chuyển {cnt} thiết bị từ {kho_nguon} sang {doi_nhan}")
                            save_all()
                            st.success(f"✅ Đã cấp phát thành công {cnt} thiết bị!")
                            st.rerun()
            else:
                st.warning(f"Kho '{kho_nguon}' hiện không còn vật tư nào trạng thái 'Dưới kho'.")

        # === CHẾ ĐỘ 2: NẠP EXCEL (PHẦN BẠN CẦN ĐÂY) ===
        else:
            st.info("💡 File Excel cần có cột: 'Số_Seri', 'Mã_TB' (Tùy chọn), 'Đến_Đơn_Vị', 'Ghi_Chú'")
            
            # Tạo file mẫu
            mau_cp = pd.DataFrame({
                'Số_Seri': ['123456', '789012'],
                'Mã_TB': ['T24 - HHM11', 'T30 - CE-14'],
                'Đến_Đơn_Vị': ['PB0601 Tân An', 'PB0602 Thủ Thừa'],
                'Ghi_Chú': ['Cấp đợt 1', 'Cấp bổ sung']
            })
            st.download_button("📥 Tải file mẫu Cấp phát (.xlsx)", get_sample_excel(mau_cp), "Mau_Cap_Phat.xlsx")
            
            f_cp = st.file_uploader("Upload Excel Cấp phát", type=["xlsx"], key="upl_cp_excel")
            
            if f_cp and st.button("🚀 Thực hiện Cấp phát hàng loạt"):
                try:
                    df_up = pd.read_excel(f_cp)
                    df_up.columns = [c.strip() for c in df_up.columns]
                    
                    if 'Số_Seri' not in df_up.columns or 'Đến_Đơn_Vị' not in df_up.columns:
                        st.error("File thiếu cột bắt buộc: 'Số_Seri' hoặc 'Đến_Đơn_Vị'")
                    else:
                        count_ok = 0
                        errors = []
                        now_str = get_vn_time()
                        
                        for idx, row in df_up.iterrows():
                            seri = str(row['Số_Seri'])
                            dest = str(row['Đến_Đơn_Vị'])
                            note = str(row.get('Ghi_Chú', ''))
                            
                            # Tìm thiết bị trong kho nguồn
                            mask = (st.session_state.inventory['Vị_Trí_Kho'] == kho_nguon) & \
                                   (st.session_state.inventory['Số_Seri'] == seri) & \
                                   (st.session_state.inventory['Trạng_Thái_Luoi'] == "Dưới kho")
                            
                            found = st.session_state.inventory[mask].index
                            
                            if not found.empty:
                                i = found[0]
                                st.session_state.inventory.loc[i, 'Vị_Trí_Kho'] = dest
                                st.session_state.inventory.loc[i, 'Thoi_Gian_Cap_Phat'] = now_str
                                st.session_state.inventory.loc[i, 'Chi_Tiết_Vị_Trí'] = f"Nhận từ {kho_nguon} (Excel). {note}"
                                count_ok += 1
                            else:
                                errors.append(seri)
                        
                        if count_ok > 0:
                            luu_nhat_ky("Cấp phát (Excel)", f"Điều chuyển {count_ok} thiết bị từ {kho_nguon} theo danh sách Excel.")
                            save_all()
                            st.success(f"✅ Đã cấp phát thành công {count_ok} thiết bị!")
                        
                        if errors:
                            st.warning(f"⚠️ Có {len(errors)} seri không tìm thấy trong kho '{kho_nguon}' hoặc đã cấp rồi:")
                            st.write(errors)
                            
                except Exception as e:
                    st.error(f"Lỗi đọc file Excel: {e}")

    # --- TAB 2: LỊCH SỬ ---
    with t2:
        st.subheader("📜 Nhật ký Cấp phát gần đây")
        df_his = st.session_state.inventory[st.session_state.inventory['Thoi_Gian_Cap_Phat'] != '---'].copy()
        if not df_his.empty:
            # Sắp xếp theo thời gian giảm dần (nếu có thể parse)
            st.dataframe(
                df_his[['Thoi_Gian_Cap_Phat', 'Vị_Trí_Kho', 'Loại_VT', 'Mã_TB', 'Số_Seri', 'Chi_Tiết_Vị_Trí']],
                use_container_width=True
            )
        else:
            st.info("Chưa có dữ liệu.")

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

# --- MENU HIỆN TRƯỜNG (CẬP NHẬT TÊN TAB 2: KẾ HOẠCH SỬ DỤNG) ---
elif menu == "🛠️ Hiện trường (Seri)":
    st.header(f"🛠️ Quản lý Hiện trường: {st.session_state.user_name}")
    
    # Đổi tên Tab 2 thành "Kế hoạch sử dụng"
    t1, t2, t3 = st.tabs(["✍️ Cập nhật (Trạng thái/Seri)", "🗓️ Kế hoạch sử dụng", "⚠️ Kho Thu hồi"])
    
    # --- TAB 1: CẬP NHẬT TRẠNG THÁI & SỐ SERI (LOGIC ID) ---
    with t1:
        st.caption("Chức năng: Cập nhật Trạng thái hoặc **ĐIỀN SỐ SERI** cho các thiết bị 'Chưa nhập' (Dựa vào ID).")
        
        mode_t1 = st.radio("Chọn cách làm:", ["✍️ Sửa trực tiếp", "📁 Nạp Excel (Cập nhật theo ID)"], horizontal=True, label_visibility="collapsed", key="mode_ht_tab1_update")
        
        # === CHẾ ĐỘ 1: SỬA TRỰC TIẾP ===
        if mode_t1 == "✍️ Sửa trực tiếp":
            df_dv = st.session_state.inventory[st.session_state.inventory['Vị_Trí_Kho'] == st.session_state.user_name].copy()
            if not df_dv.empty:
                loai_chon = st.selectbox("🎯 Lọc loại vật tư", ["Tất cả"] + list(df_dv['Loại_VT'].unique()), key="loc_t1_manual")
                df_display = df_dv if loai_chon == "Tất cả" else df_dv[df_dv['Loại_VT'] == loai_chon]

                edited = st.data_editor(
                    df_display[['ID_He_Thong', 'Loại_VT', 'Mã_TB', 'Số_Seri', 'Trạng_Thái_Luoi', 'Mục_Đích', 'Chi_Tiết_Vị_Trí']],
                    column_config={
                        "ID_He_Thong": st.column_config.TextColumn("ID (Khóa chính)", disabled=True),
                        "Số_Seri": st.column_config.TextColumn("Số Seri (Sửa được)"), 
                        "Trạng_Thái_Luoi": st.column_config.SelectboxColumn("TT", options=TRANG_THAI_LIST),
                    }, 
                    disabled=['ID_He_Thong', 'Loại_VT', 'Mã_TB'], 
                    use_container_width=True, key="edit_grid_manual"
                )
                if st.button("💾 Lưu cập nhật", type="primary"):
                    confirm_dialog("hien_truong", edited)
            else:
                st.warning("Kho trống.")

        # === CHẾ ĐỘ 2: NẠP EXCEL (LOGIC: KHỚP ID -> ĐIỀN SERI) ===
        else:
            st.info("💡 Cách dùng: Tải file về (có cột ID và Seri trống) -> Điền Seri vào Excel -> Upload lên để cập nhật.")
            
            # Tải file danh sách (Bắt buộc phải có cột ID_He_Thong)
            df_my_stock = st.session_state.inventory[st.session_state.inventory['Vị_Trí_Kho'] == st.session_state.user_name].copy()
            if not df_my_stock.empty:
                mau_real = df_my_stock[['ID_He_Thong', 'Số_Seri', 'Mã_TB', 'Loại_VT', 'Trạng_Thái_Luoi', 'Mục_Đích']].copy()
                st.download_button(f"📥 Tải danh sách ID (.xlsx)", get_sample_excel(mau_real), f"Update_Seri_{st.session_state.user_name}.xlsx")

            # Upload file
            f_up = st.file_uploader("Upload Excel", type=["xlsx"], key="upl_update_seri_id")
            
            if f_up:
                try:
                    df_ex = pd.read_excel(f_up, dtype=str)
                    df_ex.columns = [c.strip().upper() for c in df_ex.columns]
                    
                    # Tìm cột quan trọng
                    col_id = next((c for c in df_ex.columns if "ID" in c), None)
                    col_seri = next((c for c in df_ex.columns if "SERI" in c), None)
                    col_tt = next((c for c in df_ex.columns if "TRẠNG" in c or "TRANG" in c), None)

                    if not col_id or not col_seri:
                        st.error("❌ File thiếu cột 'ID_He_Thong' hoặc 'Số_Seri'.")
                    else:
                        if st.button("🚀 Cập nhật ngay", type="primary"):
                            logs = []
                            count_ok = 0
                            
                            for idx, row in df_ex.iterrows():
                                target_id = str(row[col_id]).strip()
                                new_seri = str(row[col_seri]).strip().replace(".0", "")
                                
                                if not new_seri or new_seri.lower() == 'nan': continue

                                mask = (st.session_state.inventory['Vị_Trí_Kho'] == st.session_state.user_name) & \
                                       (st.session_state.inventory['ID_He_Thong'] == target_id)
                                found_idx = st.session_state.inventory[mask].index
                                
                                if not found_idx.empty:
                                    i = found_idx[0]
                                    old_seri = str(st.session_state.inventory.loc[i, 'Số_Seri'])
                                    changes = []
                                    
                                    if new_seri != old_seri:
                                        st.session_state.inventory.loc[i, 'Số_Seri'] = new_seri
                                        changes.append(f"Seri: {old_seri} -> {new_seri}")
                                    
                                    if col_tt and str(row[col_tt]) != 'nan':
                                         st.session_state.inventory.loc[i, 'Trạng_Thái_Luoi'] = str(row[col_tt])

                                    if changes:
                                        logs.append({"ID": target_id, "Chi tiết": ", ".join(changes)})
                                        count_ok += 1
                                
                            if count_ok > 0:
                                luu_nhat_ky("Cập nhật Seri (Excel)", f"Đội {st.session_state.user_name} cập nhật seri cho {count_ok} thiết bị.")
                                save_all()
                                st.success(f"✅ Đã cập nhật thành công {count_ok} số Seri!")
                                st.dataframe(pd.DataFrame(logs), use_container_width=True)
                                st.cache_data.clear()
                            else:
                                st.warning("⚠️ Không có dữ liệu nào thay đổi.")

                except Exception as e:
                    st.error(f"Lỗi: {e}")

# --- TAB 2: KẾ HOẠCH SỬ DỤNG (FULL CODE: NHẬP TAY + EXCEL) ---
    with t2:
        st.caption("Thực hiện các nghiệp vụ: Phát triển khách hàng mới hoặc Thay thế định kỳ/sự cố.")
        
        mode_t2 = st.radio("Chế độ nhập liệu:", ["✍️ Nhập thủ công (Từng cái)", "📁 Nạp Excel (Hàng loạt)"], horizontal=True, label_visibility="collapsed", key="radio_mode_v5_full")
        
        # === PHẦN 1: NHẬP THỦ CÔNG (CODE CŨ - ĐÃ ỔN) ===
        if mode_t2 == "✍️ Nhập thủ công (Từng cái)":
            # 1. Chọn nghiệp vụ
            nghiep_vu = st.radio("Chọn nghiệp vụ:", ["Lắp mới (Phát triển KH)", "Thay thế (Định kỳ/Đồng bộ/Sự cố)"], horizontal=True, key="radio_nv_v5")
            is_thay_the = "Thay thế" in nghiep_vu

            # 2. KHỐI CHỌN VẬT TƯ MỚI & MÃ CHÌ
            with st.container(border=True):
                st.subheader("🟦 1. Thông tin Thiết bị Mới & Mã Chì")
                c1, c2, c3 = st.columns(3)
                
                # Lọc kho
                df_kho_doi = st.session_state.inventory[(st.session_state.inventory['Vị_Trí_Kho'] == st.session_state.user_name) & (st.session_state.inventory['Trạng_Thái_Luoi'] == "Dưới kho")]
                lvt_list = df_kho_doi['Loại_VT'].unique()
                
                with c1: lvt_chon = st.selectbox("Loại VT", lvt_list if len(lvt_list)>0 else ["(Kho trống)"], key="sb_lvt_v5")
                
                models = df_kho_doi[df_kho_doi['Loại_VT'] == lvt_chon]['Mã_TB'].unique() if len(lvt_list)>0 else []
                with c2: model_chon = st.selectbox("Model/Chủng loại", models if len(models)>0 else ["(Hết)"], key="sb_mod_v5")
                
                seris = df_kho_doi[(df_kho_doi['Mã_TB'] == model_chon)]['Số_Seri'].unique() if model_chon != "(Hết)" else []
                with c3: seri_chon = st.selectbox("Số Seri sẽ lắp", seris if len(seris)>0 else ["(Hết)"], key="sb_ser_v5")

                st.divider()
                
                # Logic Gợi ý Mã Chì
                goi_y_chi = ["VN/N128_LA"] 
                model_upper = str(model_chon).upper()
                if any(x in model_upper for x in ["HHM", "DDS", "DTS", "DDZ", "LINKTON"]): goi_y_chi = ["VN/N309_HHM", "VN/N128_LA", "VN/N139_TN"]
                elif "VSE" in model_upper or "VINASINO" in model_upper: goi_y_chi = ["VN/N306_VSE1", "VN/N128_LA"]
                elif any(x in model_upper for x in ["CE-", "ME-", "PB", "TF", "GELEX", "EMIC"]): goi_y_chi = ["VN/N52", "VN/N128_LA", "VN/N370"]
                elif "OVE" in model_upper or "OMNI" in model_upper: goi_y_chi = ["VN/N224_3", "VN/N224_4"]
                elif "SF" in model_upper or "PSMART" in model_upper: goi_y_chi = ["VN/N370", "VN/N128_LA", "VN/N264_LA"]
                elif any(x in model_upper for x in ["A1700", "A1140", "A1120", "ELSTER"]): goi_y_chi = ["VN/N370", "VN/N14", "VN/N128_LA"]
                goi_y_chi.append("✍️ Nhập tay mã khác...")
                
                col_chi_1, col_chi_2 = st.columns([1, 2])
                with col_chi_1: chon_chi_list = st.selectbox("Gợi ý Mã Chì:", goi_y_chi)
                with col_chi_2:
                    if chon_chi_list == "✍️ Nhập tay mã khác...": ma_chi_final = st.text_input("Nhập mã chì thực tế:", placeholder="Vd: VN/N...")
                    else: ma_chi_final = st.text_input("Mã chì xác nhận:", value=chon_chi_list)
            
            # 3. KHỐI KHÁCH HÀNG
            with st.form(key="form_ht_v5"):
                st.subheader("👤 2. Thông tin Khách hàng & Mục đích")
                c_kh_1, c_kh_2, c_kh_3 = st.columns([1, 1.5, 1.5])
                with c_kh_1: tinh_chat_tram = st.selectbox("Tính chất lắp đặt (*)", ["Lắp KH sau TCC", "Lắp TCD", "Lắp TCC", "Lắp Ranh giới", "Khác"])
                with c_kh_2: kh_name = st.text_input("Tên Khách hàng / Mã KH", placeholder="Vd: Nguyễn Văn A...")
                with c_kh_3: dia_chi = st.text_input("Địa chỉ lắp đặt", placeholder="Vd: Ấp... Xã...")
                
                # 4. KHỐI THU HỒI
                old_seri, old_model, old_lvt, old_idx = None, None, None, 0
                ly_do = "Lắp mới P.Triển KH"
                if is_thay_the:
                    st.warning("🟧 3. Thông tin Công tơ Cũ (Thu hồi)")
                    rc1, rc2, rc3 = st.columns(3)
                    old_lvt = rc1.selectbox("Loại VT cũ", list(DANM_MUC_NCC.keys()), index=0, key="old_lvt_v5")
                    old_model = rc2.text_input("Model cũ", placeholder="Vd: VSE11")
                    old_idx = rc3.number_input("Chỉ số chốt", min_value=0.0, format="%.2f")
                    rc4, rc5 = st.columns([1, 2])
                    old_seri = rc4.text_input("Số Seri cũ (*Bắt buộc)")
                    ly_do = rc5.selectbox("Lý do thay thế", ["Thay định kỳ", "Thay đồng bộ", "Thay hư hỏng", "Cháy nổ", "Khác"])

                st.write("---")
                if st.form_submit_button("🚀 Cập nhật Lên lưới"):
                    if seri_chon == "(Hết)" or not seri_chon: st.error("❌ Chưa chọn thiết bị mới!")
                    elif not ma_chi_final: st.error("❌ Chưa nhập Mã chì!")
                    elif is_thay_the and not old_seri: st.error("❌ Nghiệp vụ thay thế bắt buộc nhập Seri cũ!")
                    else:
                        idx_new = st.session_state.inventory[(st.session_state.inventory['Vị_Trí_Kho'] == st.session_state.user_name) & (st.session_state.inventory['Số_Seri'] == seri_chon)].index
                        st.session_state.inventory.loc[idx_new, 'Trạng_Thái_Luoi'] = "Đã đưa lên lưới"
                        st.session_state.inventory.loc[idx_new, 'Mục_Đích'] = f"{tinh_chat_tram} - {kh_name}"
                        st.session_state.inventory.loc[idx_new, 'Chi_Tiết_Vị_Trí'] = f"Đ/c: {dia_chi}. [Chì: {ma_chi_final}]. " + (f"Thay cho: {old_seri} ({ly_do})" if is_thay_the else "Lắp mới PTKH")
                        
                        if is_thay_the:
                            deadline = (datetime.datetime.now() + datetime.timedelta(days=7)).strftime("%d/%m/%Y")
                            thu_hoi_row = pd.DataFrame([{
                                'ID_He_Thong': f"TH-{uuid.uuid4().hex[:8].upper()}", 'Năm_SX': "Thu hồi", 'Loại_VT': old_lvt, 'Mã_TB': old_model, 'Số_Seri': old_seri, 'Nhà_CC': "Lưới thu hồi", 'Nguồn_Nhap': f"KH: {kh_name}", 'Vị_Trí_Kho': st.session_state.user_name, 'Trạng_Thái_Luoi': "Vật tư thu hồi", 'Mục_Đích': "Chờ kiểm định", 'Chi_Tiết_Vị_Trí': f"Hạn trả: {deadline} (CS Chốt: {old_idx}). Lý do: {ly_do}", 'Thoi_Gian_Tao': get_vn_time(), 'Thoi_Gian_Cap_Phat': '---'
                            }])
                            st.session_state.inventory = pd.concat([st.session_state.inventory, thu_hoi_row], ignore_index=True)
                            luu_nhat_ky("Thay thế", f"Lắp {seri_chon}, Thu hồi {old_seri}")
                        else:
                            luu_nhat_ky("Lắp mới", f"Lắp {seri_chon} ({tinh_chat_tram}) cho {kh_name}")
                        
                        save_all()
                        st.success("✅ Thành công!"); st.balloons(); st.rerun()

        # === PHẦN 2: NẠP EXCEL (ĐÃ KHÔI PHỤC) ===
        else:
            st.info("💡 File Excel dùng để lắp đặt hàng loạt. Hệ thống sẽ tự tìm Seri trong kho và cập nhật.")
            
            # 1. Tạo file mẫu (Chỉ lấy hàng DƯỚI KHO)
            df_avail = st.session_state.inventory[
                (st.session_state.inventory['Vị_Trí_Kho'] == st.session_state.user_name) & 
                (st.session_state.inventory['Trạng_Thái_Luoi'] == "Dưới kho")
            ].copy()
            
            if not df_avail.empty:
                mau_inst = df_avail[['Số_Seri', 'Mã_TB', 'Loại_VT']].copy()
                mau_inst['Nghiệp_Vụ'] = 'Lắp mới'
                mau_inst['Tính_Chất'] = 'Lắp TCC' # Cột mới
                mau_inst['Tên_KH'] = ''
                mau_inst['Địa_Chỉ'] = ''
                mau_inst['Mã_Chì'] = ''
                # Cột thay thế
                mau_inst['Seri_Cũ_Thu_Hồi'] = ''
                mau_inst['Model_Cũ'] = ''
                mau_inst['Chỉ_Số_Chốt'] = ''
                mau_inst['Lý_Do_Thay'] = ''
                
                st.download_button(
                    f"📥 Tải danh sách thiết bị khả dụng (.xlsx)", 
                    get_sample_excel(mau_inst), 
                    f"DS_Lap_Dat_{st.session_state.user_name}.xlsx"
                )
            else:
                st.warning("Kho hiện không có thiết bị 'Dưới kho' nào.")

            # 2. Upload file
            f_ht = st.file_uploader("Upload Excel Lắp đặt", type=["xlsx"], key="upl_excel_lap_dat_v5")
            if f_ht and st.button("🚀 Thực hiện Lắp đặt", key="btn_exec_lap_dat"):
                try:
                    df_up = pd.read_excel(f_ht, dtype=str) # Ép kiểu chuỗi
                    df_up.columns = [c.strip() for c in df_up.columns]
                    
                    count_ok = 0
                    errors = []
                    
                    for idx, row in df_up.iterrows():
                        # Bỏ qua nếu không có tên KH
                        if pd.isna(row.get('Tên_KH')) or str(row.get('Tên_KH')).strip() == '': continue

                        seri_moi = str(row['Số_Seri']).strip().replace(".0", "")
                        nghiep_vu = str(row['Nghiệp_Vụ']).lower()
                        
                        # Tìm trong kho
                        mask_new = (st.session_state.inventory['Vị_Trí_Kho'] == st.session_state.user_name) & \
                                   (st.session_state.inventory['Số_Seri'].astype(str).str.strip() == seri_moi) & \
                                   (st.session_state.inventory['Trạng_Thái_Luoi'] == "Dưới kho")
                        found_idx = st.session_state.inventory[mask_new].index
                        
                        if found_idx.empty:
                            errors.append(f"Seri {seri_moi}: Không có trong kho hoặc đã lắp.")
                            continue
                        
                        i = found_idx[0]
                        st.session_state.inventory.loc[i, 'Trạng_Thái_Luoi'] = "Đã đưa lên lưới"
                        
                        # Cập nhật Mục Đích chuẩn
                        tc = str(row.get('Tính_Chất', 'Lắp mới'))
                        kh = str(row.get('Tên_KH', 'Unknown'))
                        st.session_state.inventory.loc[i, 'Mục_Đích'] = f"{tc} - {kh}"
                        
                        ma_chi = str(row.get('Mã_Chì', 'Chưa nhập'))
                        if ma_chi == 'nan': ma_chi = 'Chưa nhập'
                        
                        detail_note = f"Đ/c: {row.get('Địa_Chỉ','')}. [Chì: {ma_chi}]. "
                        
                        if "thay" in nghiep_vu:
                            seri_cu = str(row.get('Seri_Cũ_Thu_Hồi', ''))
                            if not seri_cu or seri_cu == 'nan':
                                errors.append(f"Seri {seri_moi}: Thay thế nhưng thiếu Seri cũ.")
                                continue
                            
                            detail_note += f"Thay cho: {seri_cu}"
                            thu_hoi_row = pd.DataFrame([{
                                'ID_He_Thong': f"TH-EX-{uuid.uuid4().hex[:6]}", 'Năm_SX': "Thu hồi", 'Loại_VT': str(row.get('Loại_VT', 'Công tơ')), 
                                'Mã_TB': str(row.get('Model_Cũ', 'Thu hồi')), 'Số_Seri': seri_cu, 'Nhà_CC': "Lưới thu hồi", 
                                'Nguồn_Nhap': f"KH: {kh}", 'Vị_Trí_Kho': st.session_state.user_name, 
                                'Trạng_Thái_Luoi': "Vật tư thu hồi", 'Mục_Đích': "Chờ kiểm định", 
                                'Chi_Tiết_Vị_Trí': f"CS chốt: {row.get('Chỉ_Số_Chốt',0)}. Lý do: {row.get('Lý_Do_Thay','')}",
                                'Thoi_Gian_Tao': get_vn_time(), 'Thoi_Gian_Cap_Phat': '---'
                            }])
                            st.session_state.inventory = pd.concat([st.session_state.inventory, thu_hoi_row], ignore_index=True)
                        else:
                            detail_note += "Lắp mới (Excel)"
                        
                        st.session_state.inventory.loc[i, 'Chi_Tiết_Vị_Trí'] = detail_note
                        count_ok += 1

                    if count_ok > 0:
                        luu_nhat_ky("Lắp đặt Excel", f"Đội {st.session_state.user_name} lắp đặt {count_ok} thiết bị.")
                        save_all()
                        st.success(f"✅ Đã xử lý thành công {count_ok} dòng!")
                        st.balloons()
                        st.rerun()
                    
                    if errors:
                        st.error(f"⚠️ Có lỗi tại {len(errors)} dòng:")
                        st.write(errors)
                        
                except Exception as e:
                    st.error(f"Lỗi file Excel: {e}")

    # --- TAB 3: GIỮ NGUYÊN ---
    with t3:
        st.subheader(f"📋 Danh sách yêu cầu của: {st.session_state.user_name}")
        my_reqs = st.session_state.requests[st.session_state.requests['Đơn_Vị'] == st.session_state.user_name].copy()
        if not my_reqs.empty:
            st.dataframe(my_reqs[['Thời_Gian_Báo', 'Tên_Vật_Tư', 'Trạng_Thái', 'Thời_Gian_Bù']], use_container_width=True)
        else:
            st.info("Chưa có yêu cầu nào.")
            
# --- MENU BÁO HỎNG (ĐỘI QLĐ) ---
elif menu == "🚨 Báo Hỏng":
    st.header(f"🚨 Báo cáo Hư hỏng & Yêu cầu Bù hàng: {st.session_state.user_name}")
    
    t1, t2 = st.tabs(["✍️ Lập phiếu báo hỏng", "📋 Lịch sử đã báo"])
    
    # --- TAB 1: LẬP PHIẾU ---
    with t1:
        st.caption("Chức năng dùng để báo cáo vật tư bị lỗi/hư hỏng trong kho hoặc khi đang thi công để xin cấp bù.")
        
        # 1. Lấy dữ liệu kho của Đội
        df_kho = st.session_state.inventory[st.session_state.inventory['Vị_Trí_Kho'] == st.session_state.user_name].copy()
        
        if not df_kho.empty:
            # Thêm cột chọn
            df_kho.insert(0, "Chọn", False)
            
            # Hiển thị bảng chọn thiết bị hỏng
            st.write("👇 **Chọn thiết bị bị hỏng:**")
            edited_bh = st.data_editor(
                df_kho[['Chọn', 'Loại_VT', 'Mã_TB', 'Số_Seri', 'Năm_SX']],
                column_config={
                    "Chọn": st.column_config.CheckboxColumn("Báo hỏng?", default=False),
                    "Mã_TB": "Model/Chủng loại"
                },
                use_container_width=True,
                key="editor_bao_hong"
            )
            
            st.write("---")
            with st.form("f_bao_hong"):
                c1, c2 = st.columns(2)
                ly_do = c1.selectbox("Nguyên nhân hỏng", ["Lỗi kỹ thuật (NSX)", "Hư hỏng do vận chuyển", "Cháy nổ/Sự cố lưới", "Màn hình không hiển thị", "Khác"])
                ghi_chu = c2.text_input("Ghi chú chi tiết (nếu có)")
                
                if st.form_submit_button("🚀 Gửi yêu cầu Bù hàng"):
                    # Lấy danh sách thiết bị được chọn
                    selected = edited_bh[edited_bh["Chọn"] == True]
                    
                    if selected.empty:
                        st.error("❌ Bạn chưa chọn thiết bị nào để báo hỏng!")
                    else:
                        # 1. Cập nhật trạng thái trong kho -> "Hàng lỗi"
                        idx_list = selected.index.tolist()
                        st.session_state.inventory.loc[idx_list, 'Trạng_Thái_Luoi'] = "Báo hỏng/Chờ bù"
                        st.session_state.inventory.loc[idx_list, 'Chi_Tiết_Vị_Trí'] = f"Báo hỏng: {ly_do}. {ghi_chu}"
                        
                        # 2. Tạo yêu cầu gửi về Admin (Bảng requests)
                        now_str = get_vn_time()
                        new_reqs = []
                        
                        for _, row in selected.iterrows():
                            new_reqs.append({
                                'Thời_Gian_Báo': now_str,
                                'Đơn_Vị': st.session_state.user_name,
                                'Loại_VT': row['Loại_VT'],
                                'Tên_Vật_Tư': f"{row['Mã_TB']} - {row['Số_Seri']}", # Ghép tên để Admin dễ đọc
                                'Nhà_CC': "---", # Có thể lấy từ inventory nếu cần
                                'Chủng_Loại': row['Mã_TB'],
                                'Số_Lượng': 1,
                                'Lý_Do': f"{ly_do} ({ghi_chu})",
                                'Trạng_Thái': "Chờ duyệt",
                                'Thời_Gian_Bù': "---"
                            })
                        
                        # Lưu vào session state requests
                        df_req_new = pd.DataFrame(new_reqs)
                        st.session_state.requests = pd.concat([st.session_state.requests, df_req_new], ignore_index=True)
                        
                        # Ghi nhật ký
                        luu_nhat_ky("Báo hỏng", f"Đội {st.session_state.user_name} báo hỏng {len(selected)} thiết bị.")
                        save_all()
                        
                        st.success(f"✅ Đã gửi báo hỏng {len(selected)} thiết bị. Vui lòng chờ Admin duyệt cấp bù!")
                        st.rerun()
        else:
            st.info("Kho của bạn hiện đang trống, không có thiết bị để báo hỏng.")

    # --- TAB 2: LỊCH SỬ ---
    with t2:
        st.subheader("📋 Danh sách các yêu cầu đã gửi")
        
        # Lọc yêu cầu của user hiện tại
        my_req = st.session_state.requests[st.session_state.requests['Đơn_Vị'] == st.session_state.user_name].copy()
        
        if not my_req.empty:
            # Sắp xếp mới nhất lên đầu
            my_req = my_req.sort_index(ascending=False)
            
            # Hàm tô màu trạng thái
            def highlight_status(val):
                color = '#ffcdd2' if val == 'Chờ duyệt' else '#c8e6c9' # Đỏ nhạt nếu chờ, Xanh nhạt nếu xong
                return f'background-color: {color}'

            st.dataframe(
                my_req[['Thời_Gian_Báo', 'Tên_Vật_Tư', 'Lý_Do', 'Trạng_Thái', 'Thời_Gian_Bù']]
                .style.applymap(highlight_status, subset=['Trạng_Thái']),
                use_container_width=True
            )
        else:
            st.info("Bạn chưa có lịch sử báo hỏng nào.")
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

# --- MENU QUẢN LÝ VĂN BẢN (GỌN NHẸ: CHỈ TRÍCH XUẤT NỘI DUNG) ---
elif menu == "📂 Quản lý Văn bản":
    st.header("📂 Kho Văn Bản & Phân Bổ")

    # 1. HÀM ĐỌC PDF (Đơn giản hóa, chỉ tìm nội dung V/v)
    def lay_noi_dung_trich_yeu(uploaded_file):
        try:
            text = ""
            with pdfplumber.open(uploaded_file) as pdf:
                # Đọc 2 trang đầu
                for i in range(min(2, len(pdf.pages))):
                    page_text = pdf.pages[i].extract_text()
                    if page_text: text += page_text + "\n"
            
            # Tìm đoạn bắt đầu bằng "V/v" và kết thúc trước từ "Kính gửi/Nơi nhận..."
            text_clean = re.sub(r'\n+', ' ', text) # Nối dòng
            match_nd = re.search(r"(V/v\s+[\s\S]+?)(?=\s*(?:Kính gửi|Nơi nhận|Tây Ninh|CỘNG HÒA))", text_clean, re.IGNORECASE)
            
            if match_nd:
                # Làm sạch khoảng trắng thừa
                return re.sub(r'\s+', ' ', match_nd.group(1)).strip()
            return ""
        except:
            return ""

    # 2. FORM UPLOAD
    with st.expander("➕ Thêm văn bản mới", expanded=True):
        file_upload = st.file_uploader("Chọn file văn bản (PDF)", type=['pdf'])
        
        auto_nd = "" # Biến chứa nội dung tự động
        
        # Xử lý file ngay khi upload
        if file_upload is not None:
            # Chỉ lấy nội dung, không lấy số/ngày nữa
            auto_nd = lay_noi_dung_trich_yeu(file_upload)
            if auto_nd:
                st.toast("✅ Đã copy xong nội dung trích yếu!")

        with st.form("upload_doc"):
            c1, c2 = st.columns([1, 2])
            
            # Phần này để trống hoặc mặc định hôm nay để bạn TỰ NHẬP
            so_hieu = c1.text_input("Số văn bản", placeholder="Nhập số (Vd: 5291/PCTN-KD)")
            ngay_ky = c1.date_input("Ngày ký", value=datetime.date.today())
            loai_vb = c1.selectbox("Loại văn bản", ["Quyết định Phân bổ", "Lệnh Điều chuyển", "Công văn", "Khác"])
            
            doi_lien_quan = c2.multiselect("Phân bổ cho Đội nào? (Ghi chú)", DANH_SACH_14_DOI)
            
            # Ô này sẽ TỰ ĐỘNG ĐIỀN nội dung máy đọc được
            mo_ta = c2.text_area("Nội dung / Trích yếu (Tự động điền)", value=auto_nd, height=100)
            
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

    # 3. DANH SÁCH VĂN BẢN (Giữ nguyên phần hiển thị đã sửa lỗi Key)
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
                        if row['ghi_chu']: st.info(f"👉 **Phân bổ:** {row['ghi_chu']}")
                        else: st.caption("_(Chung)_")
                        st.caption(f"File: {row['file_name']}")
                    with c3:
                        btn_dl, btn_del = st.columns(2)
                        with btn_dl:
                            file_q = pd.read_sql(f"SELECT file_data FROM documents WHERE id='{row['id']}'", engine)
                            if not file_q.empty and file_q.iloc[0]['file_data']:
                                st.download_button("📥", data=bytes(file_q.iloc[0]['file_data']), file_name=row['file_name'], mime='application/pdf', key=f"dl_{row['id']}_{i}")
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

# --- MENU QUẢN TRỊ DỮ LIỆU (BACKUP & RESTORE) ---
elif menu == "💾 Quản trị Dữ liệu":
    st.header("💾 Trung tâm Sao lưu & Khôi phục Dữ liệu")
    
    t1, t2 = st.tabs(["📥 Sao lưu (Backup)", "🛠️ Cấu hình & Tiện ích"])
    
    # --- TAB 1: SAO LƯU DỮ LIỆU ---
    with t1:
        st.info("💡 Chức năng này giúp bạn tải toàn bộ dữ liệu hiện tại về máy tính để lưu trữ.")
        
        c1, c2, c3 = st.columns(3)
        
        # 1. Tải Dữ liệu KHO (Inventory)
        with c1:
            st.subheader("1. Dữ liệu Kho")
            st.caption(f"Tổng: {len(st.session_state.inventory)} dòng")
            st.download_button(
                "📥 Tải File Kho (.xlsx)",
                get_sample_excel(st.session_state.inventory),
                f"Backup_KHO_{datetime.date.today()}.xlsx",
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                use_container_width=True
            )

        # 2. Tải Dữ liệu YÊU CẦU (Requests)
        with c2:
            st.subheader("2. Yêu cầu/Báo hỏng")
            st.caption(f"Tổng: {len(st.session_state.requests)} dòng")
            st.download_button(
                "📥 Tải File Requests (.xlsx)",
                get_sample_excel(st.session_state.requests),
                f"Backup_REQUESTS_{datetime.date.today()}.xlsx",
                mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                use_container_width=True
            )

        # 3. Tải NHẬT KÝ (Logs) - Phải query từ SQL vì log không lưu hết vào session
        with c3:
            st.subheader("3. Nhật ký Hoạt động")
            try:
                engine = get_engine()
                df_log_full = pd.read_sql("SELECT * FROM nhat_ky_he_thong ORDER BY id DESC", engine)
                st.caption(f"Tổng: {len(df_log_full)} dòng")
                st.download_button(
                    "📥 Tải Full Log (.xlsx)",
                    get_sample_excel(df_log_full),
                    f"Backup_LOGS_{datetime.date.today()}.xlsx",
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    use_container_width=True
                )
            except:
                st.error("Không kết nối được bảng Log.")

        st.divider()
        
        # --- NÚT TẢI ALL-IN-ONE (SIÊU TIỆN LỢI) ---
        st.subheader("📦 Tải trọn gói (All-in-One)")
        st.write("Tải 1 file Excel duy nhất chứa cả 3 sheet: Inventory, Requests và Logs.")
        
        if st.button("🚀 Tạo file Backup Tổng thể"):
            try:
                # Tạo file Excel nhiều sheet trong bộ nhớ
                output = io.BytesIO()
                with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                    st.session_state.inventory.to_excel(writer, sheet_name='INVENTORY', index=False)
                    st.session_state.requests.to_excel(writer, sheet_name='REQUESTS', index=False)
                    # Lấy log
                    try:
                        engine = get_engine()
                        df_log_full = pd.read_sql("SELECT * FROM nhat_ky_he_thong", engine)
                        df_log_full.to_excel(writer, sheet_name='LOGS', index=False)
                    except:
                        pd.DataFrame({'Lỗi': ['Không tải được log']}).to_excel(writer, sheet_name='LOGS')
                
                st.download_button(
                    "📥 Bấm để tải File Backup Tổng thể (.xlsx)",
                    data=output.getvalue(),
                    file_name=f"FULL_BACKUP_QLVT_{datetime.date.today()}.xlsx",
                    mime='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                    type="primary"
                )
            except Exception as e:
                st.error(f"Lỗi tạo file backup: {e}")

    # --- TAB 2: TIỆN ÍCH KHÁC ---
    with t2:
        st.write("🔧 **Công cụ sửa lỗi nhanh:**")
        if st.button("🔄 Làm mới bộ nhớ đệm (Reload Data)"):
            st.cache_data.clear()
            st.session_state.inventory, st.session_state.requests = load_data()
            st.success("Đã tải lại dữ liệu mới nhất từ Server!")
            st.rerun()












































































