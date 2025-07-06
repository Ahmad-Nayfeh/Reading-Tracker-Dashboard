import streamlit as st
from fpdf import FPDF, XPos, YPos
from datetime import datetime, date
import pandas as pd
import plotly.graph_objects as go
import io
import os
from PIL import Image
import arabic_reshaper
from bidi.algorithm import get_display

# --- Constants ---
FONT_NAME = "Amiri-Regular.ttf"
COVER_IMAGE = "cover_page.png"
A4_WIDTH = 210
A4_HEIGHT = 297
# --- AESTHETIC IMPROVEMENT ---
ACCENT_COLOR = (41, 128, 185) # A professional blue color
LINE_COLOR = (200, 200, 200) # A light gray for separator lines

class PDFReporter(FPDF):
    """
    A class to generate professional, multi-page PDF reports with full Arabic support,
    custom backgrounds, headers, and footers, using a local font file.
    """
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.font_path = FONT_NAME
        self.font_loaded = False
        self._setup_fonts()
        self.processed_background = None
        if os.path.exists(COVER_IMAGE):
            self._prepare_background_image()

    def _setup_fonts(self):
        if not os.path.exists(self.font_path):
            st.error(f"Font file not found! Please make sure '{self.font_path}' is in the root folder of the project.")
            self.font_loaded = False
            return
        try:
            self.add_font("Amiri", "", self.font_path, uni=True)
            self.font_loaded = True
        except Exception as e:
            st.error(f"FPDF error when adding font '{self.font_path}': {e}")
            self.font_loaded = False

    def _prepare_background_image(self):
        try:
            img = Image.open(COVER_IMAGE).convert("RGBA")
            background = Image.new("RGBA", img.size, (255, 255, 255))
            alpha = img.getchannel('A').point(lambda i: i * 0.5)
            img.putalpha(alpha)
            background.paste(img, (0, 0), img)
            buffer = io.BytesIO()
            background.convert("RGB").save(buffer, format="PNG")
            buffer.seek(0)
            self.processed_background = buffer
        except Exception as e:
            st.error(f"Could not process background image: {e}")
            self.processed_background = None

    def add_page(self, orientation="", format="", same=False):
        super().add_page(orientation, format, same)
        if self.processed_background:
            self.image(self.processed_background, 0, 0, w=A4_WIDTH, h=A4_HEIGHT)

    def _process_text(self, text):
        if not self.font_loaded: return str(text)
        if text is None: return ""
        reshaped_text = arabic_reshaper.reshape(str(text))
        return get_display(reshaped_text)

    def set_font(self, family, style="", size=0):
        if self.font_loaded and family.lower() == "amiri":
            super().set_font(family, style, size)
        else:
            super().set_font("helvetica", style, size)

    def footer(self):
        if not self.font_loaded or self.page_no() <= 1: return
        self.set_y(-15)
        self.set_font("Amiri", "", 10)
        self.set_text_color(80, 80, 80)
        self.cell(0, 10, f"{self.page_no()}", align="L")
        self.set_y(-15)
        self.cell(0, 10, self._process_text("تقرير ماراثون القراءة"), align="R")

    def _get_drawable_height(self):
        return self.h - self.t_margin - self.b_margin

    def _style_figure_for_arabic(self, fig: go.Figure):
        if not self.font_loaded: return fig
        fig.update_layout(
            font=dict(family="Amiri", size=12, color="black"),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            title=dict(font=dict(family="Amiri", size=18, color="black"), x=0.5, pad=dict(b=15)),
            xaxis=dict(title=dict(font=dict(family="Amiri", size=14, color="black")), tickfont=dict(family="Amiri", size=12, color="black"), showgrid=True, gridcolor="lightgray", gridwidth=0.5),
            yaxis=dict(title=dict(font=dict(family="Amiri", size=14, color="black")), tickfont=dict(family="Amiri", size=12, color="black"), showgrid=True, gridcolor="lightgray", gridwidth=0.5),
            margin=dict(l=60, r=60, t=80, b=60)
        )
        return fig

    def add_cover_page(self, report_type_title):
        if not self.font_loaded: return
        self.add_page()
        drawable_width = self.w - self.l_margin - self.r_margin
        content_height = (15 * 2) + 20 + 10
        top_margin = (self._get_drawable_height() - content_height) / 2 + self.t_margin
        self.set_y(top_margin)
        self.set_font("Amiri", "", 36)
        self.set_text_color(0, 0, 0)
        self.multi_cell(drawable_width, 15, self._process_text("تقرير أداء\nماراثون القراءة"), align="C")
        self.set_font("Amiri", "", 24)
        self.set_text_color(*ACCENT_COLOR)
        self.multi_cell(drawable_width, 20, self._process_text(report_type_title), align="C")
        self.set_y(A4_HEIGHT / 1.5)
        self.set_font("Amiri", "", 16)
        self.set_text_color(0, 0, 0)
        today_str = datetime.now().strftime("%Y-%m-%d")
        self.multi_cell(drawable_width, 10, self._process_text(f"تاريخ التصدير: {today_str}"), align="C")

    def add_group_info_page(self, group_stats, periods_df):
        if not self.font_loaded: return
        self.add_page()
        title_h, section_title_h, line_h, spacing_h = 15, 10, 10, 10
        content_height = title_h + 5 + spacing_h
        content_height += section_title_h + (line_h * 3) + spacing_h
        content_height += section_title_h
        content_height += (line_h * len(periods_df)) + 5 + line_h if not periods_df.empty else line_h
        top_margin = (self._get_drawable_height() - content_height) / 2 + self.t_margin
        self.set_y(top_margin)
        self.set_font("Amiri", "", 24)
        self.set_text_color(*ACCENT_COLOR)
        self.cell(0, title_h, self._process_text("معلومات المجموعة"), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*LINE_COLOR)
        self.line(self.l_margin, self.get_y() + 2, self.w - self.r_margin, self.get_y() + 2)
        self.ln(spacing_h)
        self.set_text_color(0, 0, 0)
        self.set_font("Amiri", "", 18)
        self.cell(0, section_title_h, self._process_text("إحصائيات الأعضاء"), align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font("Amiri", "", 14)
        if group_stats:
            self.cell(0, line_h, self._process_text(f"• عدد الأعضاء الكلي: {group_stats.get('total', 0)}"), align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.cell(0, line_h, self._process_text(f"• عدد الأعضاء النشطين: {group_stats.get('active', 0)}"), align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            self.cell(0, line_h, self._process_text(f"• عدد الأعضاء الخاملين: {group_stats.get('inactive', 0)}"), align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(spacing_h)
        self.set_font("Amiri", "", 18)
        self.cell(0, section_title_h, self._process_text("معلومات التحديات"), align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_font("Amiri", "", 14)
        if not periods_df.empty:
            periods_df['start_date_dt'] = pd.to_datetime(periods_df['start_date'])
            sorted_periods = periods_df.sort_values(by='start_date_dt', ascending=True)
            for _, period in sorted_periods.iterrows():
                info_line = f"• {period.get('title', 'N/A')} ({period.get('author', 'N/A')}) | الفترة: من {period.get('start_date', 'N/A')} إلى {period.get('end_date', 'N/A')}"
                self.cell(0, line_h, self._process_text(info_line), align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
            first_challenge_date = sorted_periods['start_date_dt'].min().date()
            days_since_start = (date.today() - first_challenge_date).days
            self.ln(5)
            self.set_font("Amiri", "", 12)
            self.set_text_color(80, 80, 80)
            self.cell(0, line_h, self._process_text(f"عدد الأيام منذ بداية أول تحدي: {days_since_start} يوم"), align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        else:
            self.cell(0, line_h, self._process_text("لا توجد تحديات مسجلة بعد."), align="R", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

    def add_plot(self, fig: go.Figure, width_percent=90):
        if not self.font_loaded or not fig: return None, 0
        styled_fig = self._style_figure_for_arabic(fig)
        img_bytes = styled_fig.to_image(format="png", scale=2, width=800, height=500)
        img_file = io.BytesIO(img_bytes)
        pil_img = Image.open(img_file)
        aspect_ratio = pil_img.height / pil_img.width
        page_width = self.w - self.l_margin - self.r_margin
        img_width_mm = page_width * (width_percent / 100)
        img_height_mm = img_width_mm * aspect_ratio
        x_pos = (self.w - img_width_mm) / 2
        img_file.seek(0)
        self.image(img_file, x=x_pos, w=img_width_mm)
        return img_height_mm

    def _add_kpis_page(self, data, title="ملخص الأداء والأبطال"):
        self.add_page()
        title_h, kpi_row_h, champions_title_h, champions_row_h = 15, 20, 15, 18
        champions_data = data.get('champions_data', {})
        num_champion_rows = (len(champions_data) + 1) // 2 if champions_data else 0
        content_height = title_h + 5 + (kpi_row_h * 2) + 15
        if champions_data:
            content_height += champions_title_h + (champions_row_h * num_champion_rows) + (10 * (num_champion_rows - 1))
        top_margin = (self._get_drawable_height() - content_height) / 2 + self.t_margin
        self.set_y(top_margin)
        self.set_font("Amiri", "", 24)
        self.set_text_color(*ACCENT_COLOR)
        self.cell(0, title_h, self._process_text(title), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*LINE_COLOR)
        self.line(self.l_margin, self.get_y() + 2, self.w - self.r_margin, self.get_y() + 2)
        self.set_text_color(0,0,0)
        self.add_kpi_row(data.get('kpis_main', {}))
        if data.get('kpis_secondary'):
            self.add_kpi_row(data.get('kpis_secondary', {}))
        if champions_data:
            self.add_champions_section(champions_data)

    def _add_single_plot_page(self, fig, title):
        self.add_page()
        pil_img = Image.open(io.BytesIO(fig.to_image(format="png", scale=2, width=800, height=500)))
        aspect_ratio = pil_img.height / pil_img.width
        page_width = self.w - self.l_margin - self.r_margin
        img_width_mm = page_width * 0.85
        img_height_mm = img_width_mm * aspect_ratio
        content_height = img_height_mm + 20
        top_margin = (self._get_drawable_height() - content_height) / 2 + self.t_margin
        self.set_y(top_margin)
        self.set_font("Amiri", "", 24)
        self.set_text_color(*ACCENT_COLOR)
        self.cell(0, 10, self._process_text(title), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*LINE_COLOR)
        self.line(self.l_margin, self.get_y() + 2, self.w - self.r_margin, self.get_y() + 2)
        self.ln(10)
        self.set_text_color(0,0,0)
        self.add_plot(fig, width_percent=85)

    def _add_dual_plot_page(self, fig1, title1, fig2, title2):
        self.add_page()
        page_width = self.w - self.l_margin - self.r_margin
        img_width_mm = page_width * 0.85
        pil_img1 = Image.open(io.BytesIO(fig1.to_image(format="png", scale=2, width=800, height=500)))
        img_height1_mm = img_width_mm * (pil_img1.height / pil_img1.width)
        pil_img2 = Image.open(io.BytesIO(fig2.to_image(format="png", scale=2, width=800, height=500)))
        img_height2_mm = img_width_mm * (pil_img2.height / pil_img2.width)
        content_height = (img_height1_mm + img_height2_mm) + 45
        top_margin = (self._get_drawable_height() - content_height) / 2 + self.t_margin
        self.set_y(top_margin)
        self.set_font("Amiri", "", 24)
        self.set_text_color(*ACCENT_COLOR)
        self.cell(0, 10, self._process_text(title1), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*LINE_COLOR)
        self.line(self.l_margin, self.get_y() + 2, self.w - self.r_margin, self.get_y() + 2)
        self.ln(10)
        self.set_text_color(0,0,0)
        self.add_plot(fig1, width_percent=85)
        self.ln(10)
        self.set_font("Amiri", "", 24)
        self.set_text_color(*ACCENT_COLOR)
        self.cell(0, 10, self._process_text(title2), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*LINE_COLOR)
        self.line(self.l_margin, self.get_y() + 2, self.w - self.r_margin, self.get_y() + 2)
        self.ln(10)
        self.set_text_color(0,0,0)
        self.add_plot(fig2, width_percent=85)

    def add_kpi_row(self, kpis: dict):
        if not self.font_loaded or not kpis: return
        self.ln(10)
        col_width = (self.w - self.l_margin - self.r_margin) / len(kpis)
        self.set_font("Amiri", "", 12)
        self.set_text_color(50, 50, 50)
        for label, _ in kpis.items():
            self.cell(col_width, 10, self._process_text(label), align="C")
        self.ln(10)
        self.set_font("Amiri", "", 20)
        self.set_text_color(0, 0, 0)
        for _, value in kpis.items():
            self.cell(col_width, 10, self._process_text(str(value)), align="C")
        self.ln(15)

    def add_champions_section(self, champions_data: dict):
        if not self.font_loaded or not champions_data: return
        self.ln(5)
        self.set_font("Amiri", "", 20)
        self.set_text_color(0, 0, 0)
        self.cell(0, 15, self._process_text("أبطال الماراثون"), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(5)
        page_width = self.w - self.l_margin - self.r_margin
        col_width = page_width / 2
        champions_list = list(champions_data.items())
        for i in range(0, len(champions_list), 2):
            y_pos = self.get_y()
            self.set_font("Amiri", "", 12)
            self.set_text_color(80, 80, 80)
            self.multi_cell(col_width, 8, self._process_text(champions_list[i][0]), align="C")
            self.set_xy(self.l_margin, self.get_y())
            self.set_font("Amiri", "", 16)
            self.set_text_color(0, 0, 0)
            self.multi_cell(col_width, 10, self._process_text(champions_list[i][1]), align="C")
            if i + 1 < len(champions_list):
                self.set_xy(self.l_margin + col_width, y_pos)
                self.set_font("Amiri", "", 12)
                self.set_text_color(80, 80, 80)
                self.multi_cell(col_width, 8, self._process_text(champions_list[i+1][0]), align="C")
                self.set_xy(self.l_margin + col_width, self.get_y())
                self.set_font("Amiri", "", 16)
                self.set_text_color(0, 0, 0)
                self.multi_cell(col_width, 10, self._process_text(champions_list[i+1][1]), align="C")
            self.ln(10)
        self.ln(10)
        
    def add_dashboard_report(self, data: dict):
        if not self.font_loaded: return
        self.add_cover_page("تحليل لوحة التحكم العامة")
        self.add_group_info_page(data.get('group_stats'), data.get('periods_df'))
        self._add_kpis_page(data)
        self._add_single_plot_page(data.get('fig_growth'), "نمو القراءة التراكمي")
        self._add_dual_plot_page(data.get('fig_donut'), "تركيز القراءة", data.get('fig_bar_days'), "أيام النشاط")
        self._add_dual_plot_page(data.get('fig_points_leaderboard'), "المتصدرون بالنقاط", data.get('fig_hours_leaderboard'), "المتصدرون بالساعات")

    def add_challenge_title_page(self, title, author, period, duration):
        if not self.font_loaded: return
        self.add_page()
        drawable_width = self.w - self.l_margin - self.r_margin
        content_height = (15 * 2) + 15 + (10 * 3) # Title, spacing, and 3 lines of info
        top_margin = (self._get_drawable_height() - content_height) / 2 + self.t_margin
        self.set_y(top_margin)
        self.set_font("Amiri", "", 28)
        self.set_text_color(*ACCENT_COLOR)
        self.multi_cell(drawable_width, 15, self._process_text(f"تقرير تحدي:\n{title}"), align="C")
        self.ln(15)
        self.set_font("Amiri", "", 16)
        self.set_text_color(80, 80, 80)
        self.multi_cell(drawable_width, 10, self._process_text(f"تأليف: {author}"), align="C")
        self.multi_cell(drawable_width, 10, self._process_text(f"الفترة: {period}"), align="C")
        self.multi_cell(drawable_width, 10, self._process_text(f"مدة التحدي: {duration} يوم"), align="C")

    def add_participants_page(self, all_participants, finishers, attendees):
        if not self.font_loaded: return
        self.add_page()
        title_h, header_h, line_h, spacing_h = 15, 10, 8, 10
        max_len = max(len(all_participants), len(finishers), len(attendees))
        content_height = title_h + 5 + spacing_h + header_h + 15 + (line_h * max_len)
        top_margin = (self._get_drawable_height() - content_height) / 2 + self.t_margin
        self.set_y(top_margin)
        self.set_font("Amiri", "", 24)
        self.set_text_color(*ACCENT_COLOR)
        self.cell(0, title_h, self._process_text("المشاركون في التحدي"), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.set_draw_color(*LINE_COLOR)
        self.line(self.l_margin, self.get_y() + 2, self.w - self.r_margin, self.get_y() + 2)
        self.ln(spacing_h)
        self.set_text_color(0, 0, 0)
        page_w = self.w - self.l_margin - self.r_margin
        col_w = page_w / 3
        self.set_font("Amiri", "", 14)
        self.cell(col_w, header_h, self._process_text("من حضروا النقاش"), border='B', align="C")
        self.cell(col_w, header_h, self._process_text("من أنهوا الكتاب"), border='B', align="C")
        self.cell(col_w, header_h, self._process_text("جميع المشاركين"), border='B', align="C")
        self.ln(15)
        self.set_font("Amiri", "", 11)
        self.set_text_color(50,50,50)
        for i in range(max_len):
            p_name = all_participants[i] if i < len(all_participants) else ""
            f_name = finishers[i] if i < len(finishers) else ""
            a_name = attendees[i] if i < len(attendees) else ""
            self.cell(col_w, line_h, self._process_text(a_name), align="C")
            self.cell(col_w, line_h, self._process_text(f_name), align="C")
            self.cell(col_w, line_h, self._process_text(p_name), align="C")
            self.ln()

    def add_challenge_report(self, data: dict):
        if not self.font_loaded: return
        self.add_challenge_title_page(
            title=data.get('title', ''), author=data.get('author', ''),
            period=data.get('period', ''), duration=data.get('duration', 0)
        )
        self.add_participants_page(
            all_participants=data.get('all_participants', []),
            finishers=data.get('finishers', []), attendees=data.get('attendees', [])
        )
        self._add_kpis_page({"kpis_main": data.get('kpis', {})}, title="ملخص الأداء")
        self._add_single_plot_page(data.get('fig_area'), "مجموع ساعات القراءة التراكمي")
        self._add_dual_plot_page(data.get('fig_hours'), "ساعات قراءة الأعضاء", data.get('fig_points'), "نقاط الأعضاء")
