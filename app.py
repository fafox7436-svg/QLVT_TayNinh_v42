import streamlit as st
import pandas as pd
import plotly.express as px
import datetime
import io
import os
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

# --- 2. QUẢN LÝ DỮ LIỆU ---
INV_FILE = "pc_tayninh_v42_inventory.csv"
REQ_FILE = "pc_tayninh_v42_requests.csv"

def load_data():
    inv_cols = ['ID_He_Thong', 'Năm_SX', 'Loại_VT', 'Mã_TB', 'Số_Seri', 'Nhà_CC', 'Nguồn_Nhap', 'Vị_Trí_Kho', 'Trạng_Thái_Luoi', 'Mục_Đích', 'Vị_Tiết_Chi_Tiết', 'Thoi_Gian_Tao', 'Thoi_Gian_Cap_Phat']
    req_cols = ['Thời_Gian_Báo', 'Đơn_Vị', 'Loại_VT', 'Tên_Vật_Tư', 'Nhà_CC', 'Chủng_Loại', 'Số_Lượng', 'Lý_Do', 'Trạng_Thái', 'Thời_Gian_Bù']
    
    # Tự động tạo file nếu chưa tồn tại
    if not os.path.exists(INV_FILE):
        pd.DataFrame(columns=inv_cols).to_csv(INV_FILE, index=False, encoding='utf-8-sig')
    if not os.path.exists(REQ_FILE):
        pd.DataFrame(columns=req_cols).to_csv(REQ_FILE, index=False, encoding='utf-8-sig')
        
    inv = pd.read_csv(INV_FILE)
    req = pd.read_csv(REQ_FILE)
    
    # Làm sạch dữ liệu
    for df in [inv, req]:
        for col in df.columns:
            if df[col].dtype == 'object': 
                df[col] = df[col].astype(str).str.strip()
    return inv, req
    
    # Load Inventory
    if os.path.exists(INV_FILE):
        inv = pd.read_csv(INV_FILE)
    else:
        inv = pd.DataFrame(columns=inv_cols)
        
    # Load Requests
    if os.path.exists(REQ_FILE):
        req = pd.read_csv(REQ_FILE)
    else:
        req = pd.DataFrame(columns=req_cols)
        
    # Cleanup data
    for df in [inv, req]:
        for col in df.columns:
            if df[col].dtype == 'object': 
                df[col] = df[col].astype(str).str.strip()
    return inv, req

# Khởi tạo dữ liệu vào Session State
if 'inventory' not in st.session_state:
    st.session_state.inventory, st.session_state.requests = load_data()

def save_all():
    st.session_state.inventory.to_csv(INV_FILE, index=False)
    st.session_state.requests.to_csv(REQ_FILE, index=False)

def get_sample_excel(cols):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        pd.DataFrame(columns=cols).to_excel(writer, index=False)
    return output.getvalue()

# --- 3. TRUNG TÂM XÁC NHẬN ---
@st.dialog("XÁC NHẬN NGHIỆP VỤ")
def confirm_dialog(action, data=None):
    st.warning("⚠️ Hệ thống yêu cầu xác nhận để ghi dữ liệu vào tệp gốc.")
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
                ['Số_Seri', 'Trạng_Thái_Luoi', 'Mục_Đích', 'Vị_Tiết_Chi_Tiết']] = row[['Số_Seri', 'Trạng_Thái_Luoi', 'Mục_Đích', 'Vị_Tiết_Chi_Tiết']].values
        elif action == "bao_hong":
            st.session_state.requests = pd.concat([st.session_state.requests, data], ignore_index=True)
        elif action == "duyet_hong":
            st.session_state.requests.loc[data, 'Trạng_Thái'] = "Đã bù hàng"
            st.session_state.requests.loc[data, 'Thời_Gian_Bù'] = now_s
            
        save_all()
        st.success("Dữ liệu đã được cập nhật!")
        st.rerun()

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
                st.session_state.logged_in = True
                st.session_state.user_role = "admin" if u == "admin" else "doi"
                st.session_state.user_name = u
                st.rerun()
            else:
                st.error("Mật khẩu sai!")
    st.stop()

# --- 5. SIDEBAR ---
st.sidebar.write(f"👤 Đang dùng: **{st.session_state.user_name}**")
if st.sidebar.button("Đăng xuất"):
    st.session_state.logged_in = False
    st.rerun()

if st.session_state.user_role == "admin":
    menu = st.sidebar.radio("CÔNG TY", ["📊 Giám sát & Dashboard", "📥 Nhập Kho", "🚚 Cấp Phát", "🚨 Duyệt Báo Hỏng"])
else:
    menu = st.sidebar.radio("ĐỘI QLĐ", ["🛠️ Hiện trường (Seri)", "🚨 Báo Hỏng"])

# --- 6. CHI TIẾT CHỨC NĂNG ---

# A. GIÁM SÁT (ADMIN)
if menu == "📊 Giám sát & Dashboard":
    st.header("Dashboard Giám Sát Lưới")
    df = st.session_state.inventory.copy()
    
    if not df.empty:
        # Bộ lọc để Dashboard linh hoạt hơn
        c_f1, c_f2 = st.columns(2)
        with c_f1:
            filter_loai = st.multiselect("Lọc loại vật tư", options=df['Loại_VT'].unique(), default=df['Loại_VT'].unique())
        with c_f2:
            filter_kho = st.multiselect("Lọc vị trí kho", options=df['Vị_Trí_Kho'].unique(), default=df['Vị_Trí_Kho'].unique())
            
        df_filtered = df[(df['Loại_VT'].isin(filter_loai)) & (df['Vị_Trí_Kho'].isin(filter_kho))]

        # Biểu đồ hiển thị
        c1, c2 = st.columns(2)
        with c1:
            st.plotly_chart(px.pie(df_filtered, names='Trạng_Thái_Luoi', title="Tỉ lệ Trạng thái Lưới", hole=0.3), use_container_width=True)
        
        with c2:
            # Nhóm dữ liệu theo Kho và Loại vật tư để hiện nhiều màu khác nhau
            df_chart = df_filtered.groupby(['Vị_Trí_Kho', 'Loại_VT']).size().reset_index(name='Số lượng')
            
            fig = px.bar(
                df_chart, 
                x='Vị_Trí_Kho', 
                y='Số lượng', 
                color='Loại_VT', # Phân biệt màu xanh/đỏ/tím theo từng loại vật tư
                title="Số lượng vật tư theo đơn vị & chủng loại",
                barmode='group',
                text_auto=True
            )
            st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("---")
        st.subheader("📋 Danh sách dữ liệu")
        df_filtered.insert(0, "Xóa", False)
        edited = st.data_editor(df_filtered, use_container_width=True)
        
        to_del = edited[edited["Xóa"] == True]["ID_He_Thong"].tolist()
        if to_del and st.button("🗑️ Xóa vĩnh viễn dòng chọn"):
            confirm_dialog("xoa", to_del)
    else:
        st.info("Kho đang trống.")

# B. NHẬP KHO (ADMIN)
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
                        'Thoi_Gian_Tao': now, 'Thoi_Gian_Cap_Phat': '---'
                    })
                confirm_dialog("nhap", pd.DataFrame(new_rows))
   with t2:
        # Tạo file mẫu Nhập kho
        mau_nhap = pd.DataFrame(columns=['Số_Lượng', 'Năm_SX', 'Loại_VT', 'Mã_TB', 'Nhà_CC', 'Nguồn_Nhap'])
        # Thêm một dòng ví dụ để người dùng dễ hiểu
        mau_nhap.loc[0] = [10, 2025, "Công tơ", "VSE11", "Vinasino", "EVNSPC"]
        
        st.download_button(
            label="📥 Tải file mẫu Nhập Kho (.xlsx)",
            data=get_sample_excel(mau_nhap),
            file_name="Mau_Nhap_Kho.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        f = st.file_uploader("Nạp Excel Nhập (Cần đúng các cột trong file mẫu)", type=["xlsx"])
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
                        'Thoi_Gian_Tao': now, 'Thoi_Gian_Cap_Phat': '---'
                    })
            confirm_dialog("nhap", pd.DataFrame(ex_data))

# C. CẤP PHÁT (ADMIN)
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
                # Kiểm tra tồn kho trước khi cấp
                ton_kho = len(st.session_state.inventory[(st.session_state.inventory['Vị_Trí_Kho'] == tu_k) & (st.session_state.inventory['Mã_TB'] == m_c)])
                if sl_c > ton_kho:
                    st.error(f"Không đủ tồn kho! (Hiện có: {ton_kho})")
                else:
                    confirm_dialog("cap_phat", pd.DataFrame([{'Từ_Kho': tu_k, 'Mã_TB': m_c, 'Số_Lượng': sl_c, 'Đến_Đơn_Vị': den}]))
    with t2:
        # Tạo file mẫu Cấp phát
        mau_cap = pd.DataFrame(columns=['Từ_Kho', 'Mã_TB', 'Số_Lượng', 'Đến_Đơn_Vị'])
        mau_cap.loc[0] = [CO_SO[0], "VSE11", 5, DANH_SACH_14_DOI[0]]
        
        st.download_button(
            label="📥 Tải file mẫu Cấp Phát (.xlsx)",
            data=get_sample_excel(mau_cap),
            file_name="Mau_Cap_Phat.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        f_c = st.file_uploader("Nạp Excel Cấp (Cần đúng các cột trong file mẫu)", type=["xlsx"])
        if f_c and st.button("🚀 Nạp Excel Cấp"):
            confirm_dialog("cap_phat", pd.read_excel(f_c))
# D. DUYỆT BÁO HỎNG (ADMIN)
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

# E. HIỆN TRƯỜNG (ĐỘI)
elif menu == "🛠️ Hiện trường (Seri)":
    st.header(f"Cập nhật hiện trường: {st.session_state.user_name}")
    
    # 1. Lấy dữ liệu của Đội và làm sạch dữ liệu trống để tránh lỗi data_editor
    df_dv = st.session_state.inventory[st.session_state.inventory['Vị_Trí_Kho'] == st.session_state.user_name].copy()
    df_dv = df_dv.fillna("") # Quan trọng: Chuyển các giá trị trống thành chuỗi rỗng

    if not df_dv.empty:
        # Bộ lọc loại vật tư để không bị nằm chung cột khó chọn
        c1, c2 = st.columns([1, 2])
        with c1:
            loai_vattu_list = sorted(list(df_dv['Loại_VT'].unique()))
            loai_chon = st.selectbox("🎯 Chọn loại vật tư", ["Tất cả"] + loai_vattu_list)
        
        # Lọc dữ liệu hiển thị
        if loai_chon != "Tất cả":
            df_display = df_dv[df_dv['Loại_VT'] == loai_chon]
        else:
            df_display = df_dv

        t1, t2 = st.tabs(["✍️ Cập nhật trực tiếp", "📁 Excel Hiện trường"])
        
        with t1:
            st.info(f"Đang hiển thị {len(df_display)} thiết bị {loai_chon if loai_chon != 'Tất cả' else ''}")
            
            # Cấu hình bảng sửa dữ liệu
            # Lưu ý: 'Mục_Đích' bây giờ là TextColumn để nhập tay thoải mái
            edited_df = st.data_editor(
                df_display[['ID_He_Thong', 'Loại_VT', 'Mã_TB', 'Số_Seri', 'Trạng_Thái_Luoi', 'Mục_Đích', 'Vị_Tiết_Chi_Tiết']],
                column_config={
                    "ID_He_Thong": st.column_config.TextColumn("ID", width="small", disabled=True),
                    "Loại_VT": st.column_config.TextColumn("Loại", width="small", disabled=True),
                    "Mã_TB": st.column_config.TextColumn("Model", width="medium", disabled=True),
                    "Số_Seri": st.column_config.TextColumn("Số Seri", width="medium"),
                    "Trạng_Thái_Luoi": st.column_config.SelectboxColumn(
                        "Trạng thái", 
                        options=TRANG_THAI_LIST, # Phải khớp hoàn toàn với dữ liệu trong TRANG_THAI_LIST
                        required=True
                    ),
                    "Mục_Đích": st.column_config.TextColumn("Vị trí lắp đặt (Nhập tay)", width="large"),
                    "Vị_Tiết_Chi_Tiết": st.column_config.TextColumn("Ghi chú chi tiết")
                }, 
                use_container_width=True,
                key=f"editor_{loai_chon}" # Key thay đổi theo loại để tránh lỗi cache
            )
            
            if st.button("💾 Xác nhận lưu thay đổi"):
                confirm_dialog("hien_truong", edited_df)
                
        with t2:
            st.download_button("📥 Tải mẫu dữ liệu hiện tại", df_dv.to_csv(index=False).encode('utf-8-sig'), "Kho_Doi.csv")
            f_ht = st.file_uploader("Nạp Excel hiện trường", type=["xlsx", "csv"])
            if f_ht and st.button("🚀 Nạp Excel Hiện trường"):
                df_ht = pd.read_excel(f_ht) if f_ht.name.endswith('xlsx') else pd.read_csv(f_ht)
                confirm_dialog("hien_truong", df_ht)
    else:
        st.warning("Kho của Đội hiện đang trống.")

# F. BÁO HỎNG (ĐỘI)
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
        f_h = st.file_uploader("Nạp Excel Báo hỏng (Loại_VT, Tên_Vật_Tư, Nhà_CC, Chủng_Loại, Số_Lượng, Lý_Do)", type=["xlsx"])
        if f_h and st.button("🚀 Nạp Excel Báo hỏng"):
            df_bh = pd.read_excel(f_h)
            df_bh['Thời_Gian_Báo'] = datetime.datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            df_bh['Đơn_Vị'] = st.session_state.user_name
            df_bh['Trạng_Thái'] = 'Chờ xử lý'
            df_bh['Thời_Gian_Bù'] = '---'
            confirm_dialog("bao_hong", df_bh)







