import streamlit as st
import pandas as pd
import gspread
import smtplib
import time 
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from streamlit_option_menu import option_menu

# ==========================================
# ตั้งค่าหน้าจอ (ต้องอยู่บนสุดเสมอ)
# ==========================================
st.set_page_config(page_title="TUTOR FINDER", layout="wide", page_icon="🎓")

st.markdown("""
    <style>
    [data-testid="collapsedControl"] {
        color: #FFFFFF !important;
        background-color: #0078D7 !important; 
        border-radius: 20px !important;
        padding: 5px 15px !important;
        border: 1px solid #005A9E !important;
        box-shadow: 0 4px 6px rgba(0,0,0,0.3) !important;
        transition: 0.3s;
    }
    [data-testid="collapsedControl"]:hover {
        background-color: #005A9E !important;
    }
    [data-testid="collapsedControl"]::after {
        content: " เปิดเมนู";
        font-family: sans-serif;
        font-weight: bold;
        font-size: 14px;
        margin-left: 5px;
    }
    </style>
""", unsafe_allow_html=True)

# ==========================================
# 1. การเชื่อมต่อ Google Sheets (Caching Resource)
# ==========================================
@st.cache_resource
def init_connection():
    credentials_dict = dict(st.secrets["gcp_service_account"])
    return gspread.service_account_from_dict(credentials_dict)

try:
    gc = init_connection()
    sh = gc.open("Tutor_DB")
    worksheet = sh.sheet1
except Exception as e:
    st.error(f"เกิดข้อผิดพลาดในการเชื่อมต่อ Google Sheets: {e}")
    st.stop()

# ==========================================
# 1.1 ฟังก์ชันดึงข้อมูล (Caching Data)
# ==========================================
@st.cache_data(ttl=60)
def fetch_tutor_data():
    return worksheet.get_all_records()

@st.cache_data(ttl=60)
def fetch_review_data():
    try:
        ws_reviews = sh.worksheet("Reviews")
        return ws_reviews.get_all_records()
    except:
        return []

# ==========================================
# 2. ฟังก์ชันส่ง Email แจ้ง Admin
# ==========================================
def send_admin_notification(name, subject, line_id):
    try:
        SENDER_EMAIL = st.secrets["email"]["sender"]
        SENDER_APP_PASSWORD = st.secrets["email"]["password"]
        ADMIN_EMAIL = st.secrets["email"]["admin"]

        msg = MIMEMultipart()
        msg['From'] = SENDER_EMAIL
        msg['To'] = ADMIN_EMAIL
        msg['Subject'] = f"🚀 [Tutor MVP] มีติวเตอร์สมัครใหม่: คุณ {name}"

        body = f"""
        มีการสมัครติวเตอร์ใหม่เข้ามาในระบบ (รออนุมัติ)
        
        ข้อมูลเบื้องต้น:
        - ชื่อ: {name}
        - วิชาที่สอน: {subject}
        - LINE ID: {line_id}

        📌 กรุณาตรวจสอบหลักฐาน และเปลี่ยน Status เป็น "Approved" ใน Google Sheets
        """
        msg.attach(MIMEText(body, 'plain'))

        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SENDER_EMAIL, SENDER_APP_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

# ==========================================
# 3. โครงสร้าง UI และ Logic หน้าเว็บ
# ==========================================
with st.sidebar:
    st.markdown("<h2 style='text-align: center;'>🎓 Tutor MVP</h2>", unsafe_allow_html=True)
    
    menu = option_menu(
        menu_title=None, 
        options=["ค้นหาติวเตอร์", "สมัครเป็นติวเตอร์"], 
        icons=["search", "person-lines-fill"],
        default_index=0,
        styles={
            "container": {"padding": "0!important", "background-color": "transparent"},
            "icon": {"color": "#FFD700", "font-size": "18px"},
            "nav-link": {"font-size": "16px", "text-align": "left", "margin":"0px", "--hover-color": "#333333"},
            "nav-link-selected": {"background-color": "#0078D7", "color": "white"},
        }
    )

# --- หน้าที่ 1: ค้นหาติวเตอร์ ---
if menu == "ค้นหาติวเตอร์":
    st.title("📚 ค้นหาติวเตอร์ที่ใช่สำหรับคุณ")
    
    tutor_data = fetch_tutor_data()
    review_data = fetch_review_data()
    
    if len(tutor_data) > 0:
        df_tutors = pd.DataFrame(tutor_data)
        df_reviews = pd.DataFrame(review_data) if len(review_data) > 0 else pd.DataFrame(columns=["Tutor_Line_ID", "Rating", "Comment"])
        
        if "Status" in df_tutors.columns:
            df_approved = df_tutors[df_tutors["Status"] == "Approved"].copy()
            
            if not df_approved.empty:
                if not df_reviews.empty:
                    avg_ratings = df_reviews.groupby('Tutor_Line_ID').agg(
                        Avg_Rating=('Rating', 'mean'),
                        Review_Count=('Rating', 'count')
                    ).reset_index()
                    
                    df_approved = pd.merge(df_approved, avg_ratings, left_on='Line_ID', right_on='Tutor_Line_ID', how='left')
                    df_approved['Avg_Rating'] = df_approved['Avg_Rating'].fillna(0)
                    df_approved['Review_Count'] = df_approved['Review_Count'].fillna(0)
                else:
                    df_approved['Avg_Rating'] = 0.0
                    df_approved['Review_Count'] = 0
                
                df_approved = df_approved.sort_values(by=['Avg_Rating', 'Review_Count'], ascending=[False, False])
                
                subjects_list = df_approved["Subject"].unique().tolist()
                selected_subject = st.selectbox("เลือกวิชาที่ต้องการ:", ["ดูทั้งหมด"] + subjects_list)
                
                if selected_subject != "ดูทั้งหมด":
                    df_display = df_approved[df_approved["Subject"] == selected_subject]
                else:
                    df_display = df_approved
                
                st.divider()
                
                for index, row in df_display.iterrows():
                    with st.container(border=True):
                        col_name, col_star = st.columns([3, 1])
                        with col_name:
                            st.subheader(f"🧑‍🏫 {row['Name']}")
                        with col_star:
                            st.markdown(f"### ⭐ {row['Avg_Rating']:.1f}/5")
                            st.caption(f"({int(row['Review_Count'])} รีวิว)")
                        
                        col_pic, col_info, col_review = st.columns([1.5, 3, 2])
                        with col_pic:
                            profile_pic = str(row.get('Profile_Pic', '')).strip()
                            if profile_pic.startswith('http') and len(profile_pic) > 10:
                                # ใช้ HTML img tag พร้อม referrerpolicy
                                st.markdown(f'<img src="{profile_pic}" style="width:100%; border-radius:8px;" referrerpolicy="no-referrer">', unsafe_allow_html=True)
                            else:
                                st.markdown('<img src="https://via.placeholder.com/150?text=No+Profile" style="width:100%; border-radius:8px;">', unsafe_allow_html=True)
                                
                        with col_info:
                            st.write(f"**📚 วิชาที่สอน:** {row['Subject']}")
                            st.write(f"**🎓 การศึกษา:** {row['University']}")
                            st.write("**🏆 ประวัติและผลงาน:**")
                            st.info(row['Portfolio'])
                            
                        with col_review:
                            result_pic = str(row.get('Result_Pic', '')).strip()
                            if result_pic.startswith('http') and len(result_pic) > 10:
                                st.write("**✨ ผลงาน:**")
                                # ใช้ HTML img tag พร้อม referrerpolicy
                                st.markdown(f'<img src="{result_pic}" style="width:100%; border-radius:8px;" referrerpolicy="no-referrer">', unsafe_allow_html=True)
                        
                        st.link_button(f"💬 สนใจเรียน ติดต่อ (LINE: {row['Line_ID']})", f"https://line.me/ti/p/~{row['Line_ID']}", use_container_width=True)
                        
                        with st.expander(f"💬 อ่านรีวิว / ให้คะแนนคุณ {row['Name']}"):
                            st.markdown("#### รีวิวจากนักเรียน")
                            if not df_reviews.empty:
                                tutor_reviews = df_reviews[df_reviews['Tutor_Line_ID'] == row['Line_ID']]
                                if not tutor_reviews.empty:
                                    for _, rev_row in tutor_reviews.iterrows():
                                        stars = "⭐" * int(rev_row['Rating'])
                                        st.markdown(f"{stars}")
                                        st.caption(f"💬 \"{rev_row['Comment']}\"")
                                        st.divider()
                                else:
                                    st.info("ยังไม่มีข้อความรีวิว เป็นคนแรกที่เขียนรีวิวเลย!")
                            else:
                                st.info("ยังไม่มีข้อความรีวิว เป็นคนแรกที่เขียนรีวิวเลย!")

                            st.markdown("#### 📝 เคยเรียนกับติวเตอร์ท่านนี้? รีวิวเลย!")
                            with st.form(key=f"review_form_{row['Line_ID']}"):
                                rating = st.slider("ให้คะแนน (ดาว)", min_value=1, max_value=5, value=5, key=f"slider_{row['Line_ID']}")
                                comment = st.text_area("ความรู้สึกหลังเรียน (สั้นๆ)", key=f"comment_{row['Line_ID']}")
                                submit_review = st.form_submit_button("ส่งรีวิว ⭐")
                                
                                if submit_review:
                                    try:
                                        ws_reviews = sh.worksheet("Reviews")
                                        ws_reviews.append_row([row['Line_ID'], rating, comment])
                                        st.success("ขอบคุณสำหรับรีวิวครับ! ระบบกำลังปรับปรุงข้อมูล...")
                                        st.cache_data.clear() 
                                        time.sleep(1) 
                                        st.rerun() 
                                    except Exception as e:
                                        st.error(f"เกิดข้อผิดพลาดในการบันทึกรีวิว: {e}")
            else:
                st.warning("ยังไม่มีติวเตอร์ที่ผ่านการอนุมัติในระบบขณะนี้")
        else:
            st.error("ไม่พบคอลัมน์ 'Status' ในฐานข้อมูล")
    else:
        st.info("กำลังรอติวเตอร์คนแรกของระบบ! 🚀")

# --- หน้าที่ 2: สมัครเป็นติวเตอร์ ---
elif menu == "สมัครเป็นติวเตอร์":
    st.title("✨ สมัครเข้าร่วมเป็นติวเตอร์")
    st.info("กรอกข้อมูลเบื้องต้นด้านล่างนี้ และส่งหลักฐานเพิ่มเติมให้ Admin ทาง LINE")
    
    with st.form("apply_form"):
        tutor_name = st.text_input("ชื่อ-นามสกุล / ชื่อเล่นที่ต้องการใช้")
        tutor_subject = st.text_input("วิชาที่เชี่ยวชาญ / ต้องการสอน")
        tutor_university = st.text_input("คณะ / สาขา / มหาวิทยาลัย ที่กำลังศึกษาหรือจบการศึกษา")
        tutor_portfolio = st.text_area("ประวัติการศึกษา / เกรดเฉลี่ย / ประสบการณ์สอน / ผลงานเด่น")
        tutor_line_id = st.text_input("LINE ID (สำหรับให้นักเรียนติดต่อ)")
        
        st.markdown("""
        **ขั้นตอนการส่งหลักฐาน:**
        1. กดปุ่ม 'ส่งใบสมัคร' ด้านล่าง
        2. แอด LINE Admin: `@10apivich01`
        3. ส่งรูปถ่ายบัตรประชาชน, วุฒิการศึกษา และ **รูปโปรไฟล์ / รูปรีวิว (ถ้ามี)** ให้ Admin
        """)
        
        submitted = st.form_submit_button("ส่งใบสมัคร", type="primary")
        
        if submitted:
            if not tutor_name or not tutor_subject or not tutor_university or not tutor_portfolio or not tutor_line_id:
                st.warning("กรุณากรอกข้อมูลให้ครบทุกช่องครับ")
            else:
                with st.spinner("กำลังส่งข้อมูลเข้าระบบ..."):
                    new_row = [
                        tutor_name, 
                        tutor_subject, 
                        tutor_university, 
                        tutor_portfolio, 
                        tutor_line_id, 
                        "Pending", 
                        "",        
                        ""         
                    ]
                    
                    try:
                        worksheet.append_row(new_row)
                        send_admin_notification(tutor_name, tutor_subject, tutor_line_id)
                        
                        st.success("🎉 ส่งใบสมัครสำเร็จ! ข้อมูลของคุณอยู่ในระบบแล้ว กรุณาส่งหลักฐานและรูปภาพให้ Admin")
                        st.cache_data.clear() 
                        time.sleep(2) 
                        st.rerun() 
                    except Exception as e:
                        st.error(f"เกิดข้อผิดพลาดในการส่งข้อมูล: {e}")
