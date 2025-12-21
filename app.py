import streamlit as st
import pandas as pd
import plotly.express as px
import datetime
import io
import os
import uuid

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
    
def load_data():
    inv_cols = ['ID_He_Thong', 'Năm_SX', 'Loại_VT', 'Mã_TB', 'Số_Seri', 'Nhà_CC', 'Nguồn_Nhap', 'Vị_Trí_Kho', 'Trạng_Thái_Luoi', 'Mục_Đích', 'Chi_Tiết_Vị_Trí', 'Thoi_Gian_Tao', 'Thoi_Gian_Cap_Phat']
    req_cols = ['ID', 'Thời_Gian_Báo', 'Đơn_Vị', 'Loại_VT', 'Tên_Vật_Tư', 'Nhà_CC', 'Chủng_Loại', 'Số_Lượng', 'Lý_Do', 'Trạng_Thái', 'Thời_Gian_Bù']
    
    engine = get_engine()
    try:
        inv = pd.read_sql("SELECT * FROM inventory", engine)
        req = pd.read_sql("SELECT * FROM requests", engine)
        
        # Đồng bộ lại tên cột từ SQL (thường là viết thường) sang App
        if not inv.empty: inv.columns = inv_cols
        if not req.empty: req.columns = req_cols
            
        return inv.fillna(""), req.fillna("")
    except Exception as e:
        # Nếu lỗi (ví dụ chưa có bảng), hiện thông báo thay vì im lặng xóa dữ liệu
        st.warning(f"Chưa có dữ liệu cũ trên Cloud: {e}")
        return pd.DataFrame(columns=inv_cols), pd.DataFrame(columns=req_cols)

if 'inventory' not in st.session_state:
    st.session_state.inventory, st.session_state.requests = load_data()

def save_all():
    engine = get_engine()
    # Chuyển tên cột về viết thường (SQL chuẩn)
    inv_save = st.session_state.inventory.copy()
    inv_save.columns = [c.lower() for c in inv_save.columns]
    
    req_save = st.session_state.requests.copy()
    if 'ID' in req_save.columns: 
        req_save = req_save.drop(columns=['ID'])
    req_save.columns = [c.lower() for c in req_save.columns]

    try:
        # engine.begin() sẽ tự động COMMIT khi hoàn tất, giúp dữ liệu không bị mất khi F5
        with engine.begin() as conn:
            inv_save.to_sql('inventory', conn, if_exists='replace', index=False)
            req_save.to_sql('requests', conn, if_exists='replace', index=False)
        st.toast("✅ Đã đồng bộ dữ liệu xuống Database!")
    except Exception as e:
        st.error(f"❌ Lỗi lưu dữ liệu: {e}")

# --- 4. TRUNG TÂM XÁC NHẬN ---
@st.dialog("XÁC NHẬN NGHIỆP VỤ")
def confirm_dialog(action, data=None):
    st.warning("⚠️ Hệ thống yêu cầu xác nhận để ghi dữ liệu lên Google Sheets.")
    if st.button("✅ XÁC NHẬN", use_container_width=True):
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
        elif action == "bao_hong":
            st.session_state.requests = pd.concat([st.session_state.requests, data], ignore_index=True)
        elif action == "duyet_hong":
            st.session_state.requests.loc[data, 'Trạng_Thái'] = "Đã bù hàng"
            st.session_state.requests.loc[data, 'Thời_Gian_Bù'] = now_s
            
        save_all()
        st.success("Dữ liệu đã được đồng bộ trực tuyến!")
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
    menu = st.sidebar.radio("CÔNG TY", ["📊 Giám sát & Dashboard", "📂 Quản lý Văn bản", "📥 Nhập Kho", "🚚 Cấp Phát", "🚨 Duyệt Báo Hỏng", "🔄 Kho Bảo Hành/Hoàn Trả"])
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
elif menu == "📦 Hoàn Trả/Bảo Hành":
    st.header(f"📦 Yêu cầu Hoàn trả / Bảo hành: {st.session_state.user_name}")
    
    # Lấy danh sách vật tư hiện đang ở Đội
    df_dv = st.session_state.inventory[st.session_state.inventory['Vị_Trí_Kho'] == st.session_state.user_name].copy()
    
    if not df_dv.empty:
        st.info("💡 Chọn các thiết bị cần trả lại hoặc gửi đi bảo hành.")
        
        # Thêm cột "Chọn" để người dùng tích vào
        df_dv.insert(0, "Chọn", False)
        
        # Cấu hình bảng hiển thị (QUAN TRỌNG: Phải có Mã_TB để không bị mất cột Model)
        cols_show = ['Chọn', 'ID_He_Thong', 'Loại_VT', 'Mã_TB', 'Số_Seri', 'Trạng_Thái_Luoi']
        
        edited_return = st.data_editor(
            df_dv[cols_show],
            column_config={
                "Chọn": st.column_config.CheckboxColumn("Trả về?", default=False),
                "Mã_TB": st.column_config.TextColumn("Model/Mã TB"), # Đảm bảo hiện cột Model
            },
            use_container_width=True,
            disabled=['ID_He_Thong', 'Loại_VT', 'Mã_TB', 'Số_Seri', 'Trạng_Thái_Luoi'],
            key="return_editor"
        )
        
        st.write("---")
        c1, c2 = st.columns(2)
        with c1:
            ly_do = st.selectbox("📌 Lý do hoàn trả", 
                                ["Thiết bị hỏng/Lỗi", "Không phù hợp nhu cầu", "Thừa vật tư", "Bảo hành định kỳ", "Thu hồi về kho"])
        with c2:
            kho_den = st.selectbox("🚚 Chuyển về kho", CO_SO) # Danh sách kho (Cơ sở 1, 2...)

        # Nút xác nhận gửi
        if st.button("🚀 Gửi yêu cầu chuyển trả", type="primary"):
            # Lấy danh sách ID các dòng được chọn
            selected_ids = edited_return[edited_return["Chọn"] == True]["ID_He_Thong"].tolist()
            
            if not selected_ids:
                st.warning("⚠️ Vui lòng chọn ít nhất 1 vật tư để trả!")
            else:
                # Cập nhật trạng thái trong Database
                # Logic: Đổi vị trí kho thành "ĐANG CHUYỂN..." để Admin nhận biết
                idx = st.session_state.inventory[st.session_state.inventory['ID_He_Thong'].isin(selected_ids)].index
                
                st.session_state.inventory.loc[idx, 'Vị_Trí_Kho'] = f"ĐANG CHUYỂN: {kho_den}"
                st.session_state.inventory.loc[idx, 'Chi_Tiết_Vị_Trí'] = f"Lý do: {ly_do} (Từ: {st.session_state.user_name})"
                st.session_state.inventory.loc[idx, 'Trạng_Thái_Luoi'] = "Đang vận chuyển"
                
                save_all() # Lưu ngay lập tức để tránh mất dữ liệu
                st.success(f"✅ Đã gửi {len(selected_ids)} thiết bị về {kho_den}!")
                st.rerun()
    else:
        st.success("Kho của đơn vị hiện đang trống, không có gì để trả.")

# --- CHỨC NĂNG DÀNH CHO ADMIN: NHẬN HÀNG TRẢ VỀ ---
elif menu == "📦 Hoàn Trả/Bảo Hành":
    st.header(f"📦 Yêu cầu Hoàn trả / Bảo hành: {st.session_state.user_name}")
    
    # Chia tab
    t1, t2 = st.tabs(["✍️ Chọn từ danh sách", "📁 Nạp từ Excel"])
    
    # --- TAB 1: CHỌN TAY (Code cũ đã sửa lại chút cho gọn) ---
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
                ly_do = st.selectbox("📌 Lý do hoàn trả", ["Thiết bị hỏng/Lỗi", "Không phù hợp nhu cầu", "Thừa vật tư", "Bảo hành định kỳ"], key="ld_1")
            with c2:
                kho_den = st.selectbox("🚚 Chuyển về kho", CO_SO, key="kd_1")

            if st.button("🚀 Gửi yêu cầu (Chọn tay)"):
                selected_ids = edited_return[edited_return["Chọn"] == True]["ID_He_Thong"].tolist()
                if selected_ids:
                    idx = st.session_state.inventory[st.session_state.inventory['ID_He_Thong'].isin(selected_ids)].index
                    st.session_state.inventory.loc[idx, 'Vị_Trí_Kho'] = f"ĐANG CHUYỂN: {kho_den}"
                    st.session_state.inventory.loc[idx, 'Chi_Tiết_Vị_Trí'] = f"Lý do: {ly_do} (Từ: {st.session_state.user_name})"
                    save_all()
                    st.success(f"Đã gửi {len(selected_ids)} thiết bị!")
                    st.rerun()
                else:
                    st.warning("Chưa chọn thiết bị nào!")
        else:
            st.info("Kho trống.")

    # --- TAB 2: NẠP TỪ EXCEL (MỚI) ---
    with t2:
        st.write("Dùng khi cần trả hàng loạt thiết bị (Ví dụ: Thanh lý, thu hồi dự án lớn).")
        
        # Tạo nút tải file mẫu
        mau_tra = pd.DataFrame(columns=['Mã_TB', 'Số_Seri', 'Lý_Do', 'Chuyển_Về_Kho'])
        mau_tra.loc[0] = ["VSE11", "123456", "Hỏng màn hình", CO_SO[0]]
        st.download_button("📥 Tải file mẫu Hoàn trả (.xlsx)", get_sample_excel(mau_tra), "Mau_Hoan_Tra.xlsx")
        
        f_tra = st.file_uploader("Upload Excel Hoàn trả", type=["xlsx"])
        
        if f_tra and st.button("🚀 Xử lý file Excel"):
            df_upload = pd.read_excel(f_tra)
            # Chuẩn hóa tên cột
            df_upload.columns = [c.strip() for c in df_upload.columns]
            
            count_ok = 0
            list_errors = []
            
            for index, row in df_upload.iterrows():
                # Tìm thiết bị trong kho của User khớp Model và Seri
                mask = (
                    (st.session_state.inventory['Vị_Trí_Kho'] == st.session_state.user_name) & 
                    (st.session_state.inventory['Mã_TB'] == str(row['Mã_TB'])) & 
                    (st.session_state.inventory['Số_Seri'] == str(row['Số_Seri']))
                )
                
                found_idx = st.session_state.inventory[mask].index
                
                if not found_idx.empty:
                    # Lấy cái đầu tiên tìm thấy
                    i = found_idx[0]
                    st.session_state.inventory.loc[i, 'Vị_Trí_Kho'] = f"ĐANG CHUYỂN: {row['Chuyển_Về_Kho']}"
                    st.session_state.inventory.loc[i, 'Chi_Tiết_Vị_Trí'] = f"Excel: {row['Lý_Do']} (Từ: {st.session_state.user_name})"
                    st.session_state.inventory.loc[i, 'Trạng_Thái_Luoi'] = "Đang vận chuyển"
                    count_ok += 1
                else:
                    list_errors.append(f"Dòng {index+2}: Không tìm thấy {row['Mã_TB']} - Seri: {row['Số_Seri']} trong kho của bạn.")
            
            if count_ok > 0:
                save_all()
                st.success(f"✅ Đã gửi thành công {count_ok} thiết bị!")
            
            if list_errors:
                with st.expander("⚠️ Các dòng bị lỗi (Không tìm thấy trong kho)", expanded=True):
                    for e in list_errors:
                        st.write(e)
            
            if count_ok > 0:
                st.rerun() # Tải lại trang để cập nhật

elif menu == "📂 Quản lý Văn bản":
    st.header("Kho Lưu Trữ Văn Bản Phân Bổ / Điều Chuyển")
    
    # 1. Form Upload văn bản mới
    with st.expander("➕ Thêm văn bản mới", expanded=False):
        with st.form("upload_doc"):
            c1, c2 = st.columns(2)
            loai_vb = c1.selectbox("Loại văn bản", ["Quyết định Phân bổ", "Lệnh Điều chuyển", "Biên bản Thu hồi/Bảo hành", "Khác"])
            so_hieu = c2.text_input("Số hiệu văn bản (Số QĐ)")
            ngay_ky = c1.date_input("Ngày ký").strftime("%d/%m/%Y")
            mo_ta = c2.text_input("Trích yếu / Nội dung")
            file_upload = st.file_uploader("Chọn file đính kèm (PDF, Docx)", type=['pdf', 'docx', 'xlsx', 'jpg'])
            
            if st.form_submit_button("Lưu trữ văn bản"):
                if file_upload is None:
                    st.error("Vui lòng đính kèm file văn bản gốc!")
                else:
                    engine = get_engine()
                    # Đọc file thành dạng nhị phân (binary)
                    file_bytes = file_upload.getvalue()
                    
                    doc_data = pd.DataFrame([{
                        'id': str(uuid.uuid4()),
                        'loai_vb': loai_vb,
                        'so_hieu': so_hieu,
                        'ngay_ky': ngay_ky,
                        'mo_ta': mo_ta,
                        'file_data': file_bytes, # Lưu nhị phân
                        'file_name': file_upload.name,
                        'nguoi_upload': st.session_state.user_name,
                        'thoi_gian_up': datetime.datetime.now().strftime("%d/%m/%Y %H:%M")
                    }])
                    
                    # Lưu vào bảng documents
                    with engine.begin() as conn:
                        doc_data.to_sql('documents', conn, if_exists='append', index=False)
                    st.success("Đã lưu trữ văn bản thành công!")
                    st.rerun()

    # 2. Danh sách văn bản đã lưu
    st.subheader("🗃 Danh sách văn bản")
    engine = get_engine()
    try:
        # Chỉ lấy thông tin, KHÔNG lấy cột file_data để tránh lag
        df_docs = pd.read_sql("SELECT id, loai_vb, so_hieu, ngay_ky, mo_ta, file_name, nguoi_upload, thoi_gian_up FROM documents ORDER BY thoi_gian_up DESC", engine)
        
        if not df_docs.empty:
            for i, row in df_docs.iterrows():
                with st.container(border=True):
                    c1, c2, c3, c4 = st.columns([2, 2, 3, 1])
                    c1.write(f"**{row['so_hieu']}**")
                    c1.caption(row['ngay_ky'])
                    c2.info(row['loai_vb'])
                    c3.write(row['mo_ta'])
                    c3.caption(f"Up bởi: {row['nguoi_upload']}")
                    
                    # Nút tải về
                    with c4:
                        # Truy vấn lại DB để lấy file_data của đúng dòng này khi bấm nút
                        if st.button("📥 Tải", key=f"dl_{row['id']}"):
                            file_query = pd.read_sql(f"SELECT file_data, file_name FROM documents WHERE id='{row['id']}'", engine)
                            if not file_query.empty:
                                file_content = file_query.iloc[0]['file_data']
                                file_n = file_query.iloc[0]['file_name']
                                st.download_button(
                                    label="Bấm để lưu",
                                    data=file_content,
                                    file_name=file_n,
                                    mime='application/octet-stream',
                                    key=f"btn_dl_{row['id']}"
                                )
        else:
            st.info("Chưa có văn bản nào được lưu.")
    except Exception as e:
        st.error(f"Chưa tạo bảng documents hoặc lỗi kết nối: {e}")




























