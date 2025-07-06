import streamlit as st
from fpdf import FPDF, XPos, YPos
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
import io
import os
from PIL import Image
import arabic_reshaper
from bidi.algorithm import get_display

# --- Constants ---
# We will now use the local font file.
FONT_NAME = "Amiri-Regular.ttf"
COVER_IMAGE = "cover_page.png"
A4_WIDTH = 210
A4_HEIGHT = 297

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
        """
        Loads the local Arabic font file and adds it to the PDF object.
        """
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
        """
        Loads the background image, sets its opacity to 50%, and stores it
        in memory for reuse.
        """
        try:
            img = Image.open(COVER_IMAGE).convert("RGBA")
            background = Image.new("RGBA", img.size, (255, 255, 255))
            alpha = img.getchannel('A')
            alpha = alpha.point(lambda i: i * 0.5) # 50% opacity
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
        """Overrides the default add_page to include the background."""
        super().add_page(orientation, format, same)
        if self.processed_background:
            self.image(self.processed_background, 0, 0, w=A4_WIDTH, h=A4_HEIGHT)

    def _process_text(self, text):
        """Processes Arabic text for correct rendering (reshaping and bidi)."""
        if not self.font_loaded: return str(text)
        if text is None:
            return ""
        reshaped_text = arabic_reshaper.reshape(str(text))
        bidi_text = get_display(reshaped_text)
        return bidi_text

    def set_font(self, family, style="", size=0):
        """Overrides set_font to ensure the custom font is used if loaded."""
        if self.font_loaded and family.lower() == "amiri":
            super().set_font(family, style, size)
        else:
            # Fallback to a built-in font if Amiri is not available
            super().set_font("helvetica", style, size)

    def footer(self):
        """Adds a footer with page number to each page."""
        if not self.font_loaded: return
        if self.page_no() > 1:
            self.set_y(-15)
            self.set_font("Amiri", "", 10)
            self.set_text_color(80, 80, 80)
            
            self.cell(0, 10, f"{self.page_no()}", align="L")
            self.set_y(-15)
            self.cell(0, 10, self._process_text("تقرير ماراثون القراءة"), align="R")

    def add_cover_page(self):
        """Adds the main cover page of the report."""
        if not self.font_loaded: return
        self.add_page()
        self.set_font("Amiri", "", 36)
        self.set_text_color(0, 0, 0)
        self.set_y(A4_HEIGHT / 3)
        self.multi_cell(0, 15, self._process_text("تقرير أداء\nماراثون القراءة"), align="C")
        
        self.set_font("Amiri", "", 16)
        self.set_y(A4_HEIGHT / 1.5)
        today_str = datetime.now().strftime("%Y-%m-%d")
        self.multi_cell(0, 10, self._process_text(f"تاريخ التصدير: {today_str}"), align="C")

    def add_table_of_contents(self, toc_items):
        """Adds a table of contents page."""
        if not self.font_loaded: return
        self.add_page()
        self.set_font("Amiri", "", 28)
        self.set_text_color(0, 0, 0)
        self.set_y(30)
        self.cell(0, 15, self._process_text("فهرس المحتويات"), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.ln(20)

        self.set_font("Amiri", "", 18)
        for item in toc_items:
            self.cell(0, 12, self._process_text(f"- {item}"), new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="R")
            self.ln(5)

    def add_section_divider(self, title):
        """Adds a full page dedicated to a section title."""
        if not self.font_loaded: return
        self.add_page()
        self.set_font("Amiri", "", 32)
        self.set_text_color(0, 0, 0)
        self.set_y(A4_HEIGHT / 2.5)
        self.multi_cell(0, 20, self._process_text(title), align="C")

    def create_arabic_ready_plot(self, fig: go.Figure, title="", x_title="", y_title=""):
        """
        إنشاء رسم بياني جاهز للعربية مع إعدادات محسنة
        """
        if not self.font_loaded:
            return fig
        
        # تطبيق الإعدادات المحسنة
        fig.update_layout(
            title=dict(
                text=self._process_text(title) if title else "",
                font=dict(family="Amiri", size=18, color="black"),
                x=0.5,  # توسيط العنوان
                y=0.95
            ),
            xaxis=dict(
                title=dict(
                    text=self._process_text(x_title) if x_title else "",
                    font=dict(family="Amiri", size=14, color="black")
                ),
                tickfont=dict(family="Amiri", size=12, color="black"),
                showgrid=True,
                gridcolor="lightgray",
                gridwidth=0.5
            ),
            yaxis=dict(
                title=dict(
                    text=self._process_text(y_title) if y_title else "",
                    font=dict(family="Amiri", size=14, color="black")
                ),
                tickfont=dict(family="Amiri", size=12, color="black"),
                showgrid=True,
                gridcolor="lightgray",
                gridwidth=0.5
            ),
            font=dict(family="Amiri", size=12, color="black"),
            paper_bgcolor='white',
            plot_bgcolor='white',
            margin=dict(l=60, r=60, t=80, b=60)
        )
        
        # معالجة البيانات النصية العربية
        for trace in fig.data:
            if hasattr(trace, 'x') and trace.x is not None:
                if isinstance(trace.x, (list, tuple)) and len(trace.x) > 0:
                    if isinstance(trace.x[0], str):
                        trace.x = [self._process_text(str(x)) for x in trace.x]
            
            if hasattr(trace, 'y') and trace.y is not None:
                if isinstance(trace.y, (list, tuple)) and len(trace.y) > 0:
                    if isinstance(trace.y[0], str):
                        trace.y = [self._process_text(str(y)) for y in trace.y]
        
        return fig

    def add_plot(self, fig: go.Figure, width_percent=90, title="", x_title="", y_title=""):
        """Adds a Plotly figure to the PDF, ensuring Arabic fonts are used."""
        if not self.font_loaded: return
        if fig:
            # تحسين الرسم البياني للعربية
            enhanced_fig = self.create_arabic_ready_plot(fig, title, x_title, y_title)
            
            # --- تحديث إعدادات الخط للرسم البياني ---
            enhanced_fig.update_layout(
                font=dict(
                    family="Amiri",
                    size=12,
                    color="black"
                ),
                title=dict(
                    font=dict(
                        family="Amiri",
                        size=16,
                        color="black"
                    )
                ),
                xaxis=dict(
                    title=dict(
                        font=dict(
                            family="Amiri",
                            size=14,
                            color="black"
                        )
                    ),
                    tickfont=dict(
                        family="Amiri",
                        size=12,
                        color="black"
                    )
                ),
                yaxis=dict(
                    title=dict(
                        font=dict(
                            family="Amiri",
                            size=14,
                            color="black"
                        )
                    ),
                    tickfont=dict(
                        family="Amiri",
                        size=12,
                        color="black"
                    )
                ),
                paper_bgcolor='rgba(0,0,0,0)', 
                plot_bgcolor='rgba(0,0,0,0)'
            )
            
            # تحديث النص العربي إذا كان موجوداً
            if enhanced_fig.layout.title.text:
                enhanced_fig.layout.title.text = self._process_text(enhanced_fig.layout.title.text)
            
            if enhanced_fig.layout.xaxis.title.text:
                enhanced_fig.layout.xaxis.title.text = self._process_text(enhanced_fig.layout.xaxis.title.text)
                
            if enhanced_fig.layout.yaxis.title.text:
                enhanced_fig.layout.yaxis.title.text = self._process_text(enhanced_fig.layout.yaxis.title.text)
            
            # معالجة تسميات المحاور إذا كانت عربية
            if hasattr(enhanced_fig.data[0], 'x') and enhanced_fig.data[0].x is not None:
                # للتأكد من أن تسميات المحور السيني تظهر بشكل صحيح
                x_values = enhanced_fig.data[0].x
                if isinstance(x_values, (list, tuple)) and len(x_values) > 0:
                    if isinstance(x_values[0], str):
                        processed_x = [self._process_text(str(x)) for x in x_values]
                        enhanced_fig.data[0].x = processed_x
            
            # إنشاء الصورة مع دقة عالية
            img_bytes = enhanced_fig.to_image(format="png", scale=2, width=800, height=600)
            img_file = io.BytesIO(img_bytes)
            
            page_width = self.w - self.l_margin - self.r_margin
            img_width = page_width * (width_percent / 100)
            x_pos = (self.w - img_width) / 2
            
            self.image(img_file, x=x_pos, w=img_width)
            self.ln(5)

    def add_kpi_row(self, kpis: dict):
        """Adds a row of Key Performance Indicators."""
        if not self.font_loaded or not kpis: return
        self.ln(10)
        col_width = (self.w - self.l_margin - self.r_margin) / len(kpis)
        
        self.set_font("Amiri", "", 12)
        self.set_text_color(50, 50, 50)
        for label, value in kpis.items():
            self.cell(col_width, 10, self._process_text(label), align="C")
        self.ln(10)

        self.set_font("Amiri", "", 20)
        self.set_text_color(0, 0, 0)
        for label, value in kpis.items():
            self.cell(col_width, 10, self._process_text(str(value)), align="C")
        self.ln(15)

    def add_champions_section(self, champions_data: dict):
        """Adds a formatted section for marathon champions."""
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
            
            # --- First Champion in Row ---
            self.set_font("Amiri", "", 12)
            self.set_text_color(80, 80, 80)
            self.multi_cell(col_width, 8, self._process_text(champions_list[i][0]), align="C")
            
            self.set_xy(self.l_margin, self.get_y())
            self.set_font("Amiri", "", 16)
            self.set_text_color(0, 0, 0)
            self.multi_cell(col_width, 10, self._process_text(champions_list[i][1]), align="C")

            # --- Second Champion in Row (if exists) ---
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
        """Adds the full general dashboard report section."""
        if not self.font_loaded: return
        self.add_section_divider("تحليل لوحة التحكم العامة")
        
        # --- Page 1: KPIs and Champions ---
        self.add_page()
        self.set_font("Amiri", "", 24)
        self.cell(0, 15, self._process_text("مؤشرات الأداء الرئيسية"), align="C", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        self.add_kpi_row(data.get('kpis_main', {}))
        self.add_kpi_row(data.get('kpis_secondary', {}))
        self.add_champions_section(data.get('champions_data', {}))
        
        # --- Page 2: Growth Chart ---
        self.add_page()
        self.add_plot(
            data.get('fig_growth'), 
            title="نمو القراءة التراكمي",
            x_title="التاريخ",
            y_title="مجموع الساعات"
        )

        # --- Page 3: Donut and Bar Chart ---
        self.add_page()
        self.add_plot(
            data.get('fig_donut'), 
            title="تركيز القراءة",
            width_percent=70
        )
        self.ln(10)
        self.add_plot(
            data.get('fig_bar_days'), 
            title="أيام النشاط",
            y_title="الساعات",
            width_percent=80
        )

        # --- Page 4: Leaderboard Charts ---
        self.add_page()
        self.add_plot(
            data.get('fig_points_leaderboard'),
            title="المتصدرون بالنقاط",
            x_title="النقاط"
        )
        self.ln(10)
        self.add_plot(
            data.get('fig_hours_leaderboard'),
            title="المتصدرون بالساعات",
            x_title="الساعات"
        )
