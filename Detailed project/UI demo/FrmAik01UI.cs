using System;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Windows.Forms;

namespace AIK01Demo.Forms
{
    // UI demo only: no API, database, authentication or AI processing.
    // Compatible with .NET Framework 4.7.2+ / C# 7.x.
    public class FrmAik01UI : Form
    {
        private readonly Color Blue = Color.FromArgb(35, 79, 155);
        private readonly Color BlueDark = Color.FromArgb(25, 62, 135);
        private readonly Color BlueLight = Color.FromArgb(235, 242, 255);
        private readonly Color Background = Color.FromArgb(244, 247, 252);
        private readonly Color TextDark = Color.FromArgb(24, 42, 68);
        private readonly Color Muted = Color.FromArgb(112, 133, 163);
        private readonly Color Border = Color.FromArgb(222, 230, 242);
        private Panel sidebar;
        private Panel contentHost;
        private Label pageTitle;
        private Label roleBadge;

        public FrmAik01UI()
        {
            Text = "AIK-01 - Trợ lý pháp quy";
            StartPosition = FormStartPosition.CenterScreen;
            WindowState = FormWindowState.Maximized;
            MinimumSize = new Size(1200, 760);
            BackColor = Background;
            Font = new Font("Segoe UI", 9F);
            ShowLogin();
        }

        private void ShowLogin()
        {
            Controls.Clear();
            BackColor = Background;

            Panel card = new Panel();
            card.BackColor = Color.White;
            card.Size = new Size(530, 650);
            card.Anchor = AnchorStyles.None;
            card.Padding = new Padding(38);
            card.Paint += DrawCardBorder;
            Controls.Add(card);

            Label logo = MakeLabel("PL", 15, FontStyle.Bold, Color.White);
            logo.BackColor = BlueDark;
            logo.TextAlign = ContentAlignment.MiddleCenter;
            logo.Size = new Size(50, 50);
            logo.Location = new Point(38, 38);
            card.Controls.Add(logo);

            Label brand = MakeLabel("AIK-01 · TRỢ LÝ PHÁP QUY", 9, FontStyle.Bold, Muted);
            brand.Location = new Point(38, 112);
            brand.Size = new Size(430, 24);
            card.Controls.Add(brand);

            Label title = MakeLabel("Không gian làm việc", 23, FontStyle.Regular, TextDark);
            title.Location = new Point(38, 145);
            title.Size = new Size(440, 42);
            card.Controls.Add(title);

            Label desc = MakeLabel("Đăng nhập bằng tài khoản hiện có. Vai trò được đọc từ hồ sơ backend, không thể chọn hoặc tự sửa tại giao diện.", 9.5F, FontStyle.Regular, Muted);
            desc.Location = new Point(38, 194);
            desc.Size = new Size(440, 48);
            card.Controls.Add(desc);

            AddField(card, "Tên đăng nhập", "demo_user", 260, false);
            AddField(card, "Mật khẩu", "••••••••••••••••••••••", 354, false);

            Button login = MakeButton("Đăng nhập", Blue, Color.White);
            login.Location = new Point(38, 455);
            login.Size = new Size(440, 46);
            login.Click += delegate
            {
                FrmAik01Dashboard dashboard = new FrmAik01Dashboard();
                dashboard.Show();
                Hide();
                dashboard.FormClosed += delegate { Close(); };
            };
            card.Controls.Add(login);

            Panel note = new Panel();
            note.BackColor = Color.FromArgb(255, 250, 240);
            note.BorderStyle = BorderStyle.FixedSingle;
            note.Location = new Point(38, 522);
            note.Size = new Size(440, 76);
            Label noteText = MakeLabel("Giao diện minh họa. Mật khẩu được xác minh tại backend. Phiên đăng nhập chỉ giữ token trong bộ nhớ tab và hết hạn sau tối đa một giờ.", 9, FontStyle.Regular, Color.FromArgb(145, 102, 37));
            noteText.Location = new Point(12, 10);
            noteText.Size = new Size(410, 54);
            note.Controls.Add(noteText);
            card.Controls.Add(note);

            CenterCard(card);
            Resize += delegate { CenterCard(card); };
        }

        private void CenterCard(Control card)
        {
            if (card.Parent == this)
                card.Location = new Point((ClientSize.Width - card.Width) / 2, (ClientSize.Height - card.Height) / 2);
        }

        private void AddField(Control parent, string caption, string value, int top, bool multiline)
        {
            Label label = MakeLabel(caption, 9, FontStyle.Bold, TextDark);
            label.Location = new Point(38, top);
            label.Size = new Size(440, 22);
            parent.Controls.Add(label);

            TextBox box = new TextBox();
            box.Text = value;
            box.Location = new Point(38, top + 25);
            box.Size = new Size(440, 42);
            box.Font = new Font("Segoe UI", 10F, FontStyle.Bold);
            box.BackColor = Color.FromArgb(235, 242, 252);
            box.BorderStyle = BorderStyle.FixedSingle;
            box.UseSystemPasswordChar = caption == "Mật khẩu";
            parent.Controls.Add(box);
        }

        private void DrawCardBorder(object sender, PaintEventArgs e)
        {
            Control c = (Control)sender;
            using (Pen p = new Pen(Border))
                e.Graphics.DrawRectangle(p, 0, 0, c.Width - 1, c.Height - 1);
        }

        private Label MakeLabel(string text, float size, FontStyle style, Color color)
        {
            return new Label
            {
                Text = text,
                Font = new Font("Segoe UI", size, style),
                ForeColor = color,
                AutoSize = false,
                BackColor = Color.Transparent
            };
        }

        private Button MakeButton(string text, Color back, Color fore)
        {
            Button b = new Button();
            b.Text = text;
            b.BackColor = back;
            b.ForeColor = fore;
            b.FlatStyle = FlatStyle.Flat;
            b.FlatAppearance.BorderSize = 0;
            b.Font = new Font("Segoe UI", 9F, FontStyle.Bold);
            b.Cursor = Cursors.Hand;
            return b;
        }

        private Panel MakeCard()
        {
            Panel p = new Panel();
            p.BackColor = Color.White;
            p.Padding = new Padding(22);
            p.Margin = new Padding(0, 0, 0, 18);
            p.Paint += DrawCardBorder;
            return p;
        }

        private void AddHeading(Panel parent, string eyebrow, string heading, string subtitle, int top)
        {
            Label e = MakeLabel(eyebrow.ToUpper(), 8.5F, FontStyle.Bold, Muted);
            e.Location = new Point(0, top);
            e.Size = new Size(1000, 20);
            parent.Controls.Add(e);

            Label h = MakeLabel(heading, 19, FontStyle.Regular, TextDark);
            h.Location = new Point(0, top + 23);
            h.Size = new Size(1100, 36);
            parent.Controls.Add(h);

            Label s = MakeLabel(subtitle, 9.5F, FontStyle.Regular, Muted);
            s.Location = new Point(0, top + 62);
            s.Size = new Size(1200, 28);
            parent.Controls.Add(s);
        }

        private void AddSectionTitle(Control parent, string text, int x, int y, int width)
        {
            Label l = MakeLabel(text, 12, FontStyle.Bold, TextDark);
            l.Location = new Point(x, y);
            l.Size = new Size(width, 26);
            parent.Controls.Add(l);
        }

        private DataGridView MakeGrid()
        {
            DataGridView g = new DataGridView();
            g.BackgroundColor = Color.White;
            g.BorderStyle = BorderStyle.None;
            g.GridColor = Border;
            g.EnableHeadersVisualStyles = false;
            g.ColumnHeadersDefaultCellStyle.BackColor = Color.FromArgb(248, 250, 254);
            g.ColumnHeadersDefaultCellStyle.ForeColor = Muted;
            g.ColumnHeadersDefaultCellStyle.Font = new Font("Segoe UI", 8.5F, FontStyle.Bold);
            g.DefaultCellStyle.Font = new Font("Segoe UI", 9F);
            g.DefaultCellStyle.ForeColor = TextDark;
            g.DefaultCellStyle.SelectionBackColor = BlueLight;
            g.DefaultCellStyle.SelectionForeColor = TextDark;
            g.RowHeadersVisible = false;
            g.AllowUserToAddRows = false;
            g.AllowUserToDeleteRows = false;
            g.ReadOnly = true;
            g.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill;
            g.SelectionMode = DataGridViewSelectionMode.FullRowSelect;
            g.ColumnHeadersHeight = 38;
            g.RowTemplate.Height = 38;
            return g;
        }

        private void AddMetric(Panel parent, string value, string caption, string detail, int x, int y, int w)
        {
            Panel p = new Panel();
            p.BackColor = Color.FromArgb(251, 252, 255);
            p.BorderStyle = BorderStyle.FixedSingle;
            p.Location = new Point(x, y);
            p.Size = new Size(w, 112);
            Label v = MakeLabel(value, 17, FontStyle.Bold, Color.FromArgb(166, 112, 28));
            v.Location = new Point(15, 12);
            v.Size = new Size(w - 30, 28);
            Label c = MakeLabel(caption, 9.5F, FontStyle.Regular, TextDark);
            c.Location = new Point(15, 43);
            c.Size = new Size(w - 30, 23);
            Label d = MakeLabel(detail, 8, FontStyle.Regular, Muted);
            d.Location = new Point(15, 70);
            d.Size = new Size(w - 30, 32);
            p.Controls.Add(v); p.Controls.Add(c); p.Controls.Add(d);
            parent.Controls.Add(p);
        }

        public class FrmAik01Dashboard : Form
        {
            private readonly Color Blue = Color.FromArgb(35, 79, 155);
            private readonly Color BlueDark = Color.FromArgb(25, 62, 135);
            private readonly Color BlueLight = Color.FromArgb(235, 242, 255);
            private readonly Color Background = Color.FromArgb(244, 247, 252);
            private readonly Color TextDark = Color.FromArgb(24, 42, 68);
            private readonly Color Muted = Color.FromArgb(112, 133, 163);
            private readonly Color Border = Color.FromArgb(222, 230, 242);
            private Panel sidebar, contentHost, page;
            private Label title, role;
            private string currentPage = "Hỏi đáp AI";

            public FrmAik01Dashboard()
            {
                Text = "AIK-01 - Hệ thống hỏi đáp quy chế";
                WindowState = FormWindowState.Maximized;
                MinimumSize = new Size(1200, 760);
                BackColor = Background;
                Font = new Font("Segoe UI", 9F);
                BuildShell();
                ShowPage("Hỏi đáp AI");
            }

            private Label L(string text, float size, FontStyle style, Color color)
            {
                return new Label { Text = text, Font = new Font("Segoe UI", size, style), ForeColor = color, AutoSize = false, BackColor = Color.Transparent };
            }

            private Button B(string text, Color back, Color fore)
            {
                Button b = new Button { Text = text, BackColor = back, ForeColor = fore, FlatStyle = FlatStyle.Flat, Font = new Font("Segoe UI", 9F, FontStyle.Bold), Cursor = Cursors.Hand };
                b.FlatAppearance.BorderSize = 0;
                return b;
            }

            private Panel Card()
            {
                Panel p = new Panel { BackColor = Color.White, Padding = new Padding(22), Margin = new Padding(0, 0, 0, 18) };
                p.Paint += delegate(object s, PaintEventArgs e) { using (Pen pen = new Pen(Border)) e.Graphics.DrawRectangle(pen, 0, 0, p.Width - 1, p.Height - 1); };
                return p;
            }

            private void BuildShell()
            {
                sidebar = new Panel { Dock = DockStyle.Left, Width = 307, BackColor = Color.White, Padding = new Padding(22, 24, 22, 18) };
                sidebar.Paint += delegate(object s, PaintEventArgs e) { using (Pen pen = new Pen(Border)) e.Graphics.DrawLine(pen, sidebar.Width - 1, 0, sidebar.Width - 1, sidebar.Height); };
                Controls.Add(sidebar);

                Label logo = L("PL", 13, FontStyle.Bold, Color.White);
                logo.BackColor = BlueDark; logo.TextAlign = ContentAlignment.MiddleCenter;
                logo.Location = new Point(8, 5); logo.Size = new Size(48, 48); sidebar.Controls.Add(logo);
                Label brand = L("Pháp Luật AI", 12, FontStyle.Bold, TextDark);
                brand.Location = new Point(68, 6); brand.Size = new Size(180, 24); sidebar.Controls.Add(brand);
                Label sub = L("Trợ lý quy chế", 9, FontStyle.Regular, Muted);
                sub.Location = new Point(68, 30); sub.Size = new Size(180, 22); sidebar.Controls.Add(sub);

                Label navTitle = L("KHÔNG GIAN LÀM VIỆC", 8.5F, FontStyle.Bold, Muted);
                navTitle.Location = new Point(10, 82); navTitle.Size = new Size(250, 24); sidebar.Controls.Add(navTitle);

                string[] items = { "Hỏi đáp AI", "Tài liệu pháp chế", "Quản trị hệ thống" };
                int y = 116;
                foreach (string item in items)
                {
                    Button nav = B((item == "Hỏi đáp AI" ? "✦    " : item == "Tài liệu pháp chế" ? "▤    " : "⚙    ") + item, item == currentPage ? BlueLight : Color.White, item == currentPage ? Blue : TextDark);
                    nav.TextAlign = ContentAlignment.MiddleLeft;
                    nav.Location = new Point(0, y); nav.Size = new Size(263, 56);
                    nav.Click += delegate { ShowPage(item); };
                    sidebar.Controls.Add(nav);
                    y += 64;
                }

                Panel userPanel = new Panel { Dock = DockStyle.Bottom, Height = 112, BackColor = Color.White };
                userPanel.Paint += delegate(object s, PaintEventArgs e) { using (Pen pen = new Pen(Border)) e.Graphics.DrawLine(pen, 0, 0, userPanel.Width, 0); };
                Label avatar = L("A", 11, FontStyle.Bold, Blue); avatar.BackColor = BlueLight; avatar.TextAlign = ContentAlignment.MiddleCenter;
                avatar.Location = new Point(5, 20); avatar.Size = new Size(40, 40); userPanel.Controls.Add(avatar);
                Label user = L("ADMIN_01", 9.5F, FontStyle.Bold, TextDark); user.Location = new Point(55, 17); user.Size = new Size(180, 22); userPanel.Controls.Add(user);
                Label userRole = L("Quản trị viên", 8.5F, FontStyle.Regular, Muted); userRole.Location = new Point(55, 39); userRole.Size = new Size(180, 20); userPanel.Controls.Add(userRole);
                Label logout = L("Đổi hồ sơ / thoát", 9, FontStyle.Regular, Muted); logout.Location = new Point(8, 76); logout.Size = new Size(180, 22); userPanel.Controls.Add(logout);
                sidebar.Controls.Add(userPanel);

                contentHost = new Panel { Dock = DockStyle.Fill, BackColor = Background, Padding = new Padding(55, 28, 55, 20), AutoScroll = true };
                Controls.Add(contentHost);
                contentHost.BringToFront();
                sidebar.BringToFront();
            }

            private void ShowPage(string name)
            {
                currentPage = name;
                contentHost.Controls.Clear();
                page = new Panel { Location = new Point(0, 0), Width = Math.Max(900, contentHost.ClientSize.Width - 110), Height = 1700, BackColor = Background, Anchor = AnchorStyles.Top | AnchorStyles.Left | AnchorStyles.Right };
                contentHost.Controls.Add(page);
                title = L(name, 21, FontStyle.Regular, TextDark);
                title.Location = new Point(0, 34); title.Size = new Size(900, 42); page.Controls.Add(title);
                Label eyebrow = L("AIK-01 · HỆ THỐNG HỎI ĐÁP QUY CHẾ", 8.5F, FontStyle.Bold, Muted);
                eyebrow.Location = new Point(0, 5); eyebrow.Size = new Size(700, 22); page.Controls.Add(eyebrow);
                role = L("●  Quản trị viên", 9, FontStyle.Bold, Color.FromArgb(65, 145, 112));
                role.TextAlign = ContentAlignment.MiddleCenter; role.Location = new Point(page.Width - 180, 15); role.Size = new Size(160, 36); page.Controls.Add(role);

                Panel notice = new Panel { BackColor = Color.FromArgb(241, 246, 255), Location = new Point(0, 100), Size = new Size(page.Width - 5, 48), BorderStyle = BorderStyle.FixedSingle };
                Label noticeText = L("Vai trò được đọc từ tài khoản backend đã xác thực; API kiểm tra quyền trên từng thao tác.", 9, FontStyle.Regular, Muted);
                noticeText.Location = new Point(15, 12); noticeText.Size = new Size(notice.Width - 30, 24); notice.Controls.Add(noticeText); page.Controls.Add(notice);

                if (name == "Hỏi đáp AI") BuildChat();
                else if (name == "Tài liệu pháp chế") BuildDocuments();
                else BuildAdmin();
            }

            private void PageHeading(string eyebrow, string heading, string subtitle, int y)
            {
                Label e = L(eyebrow.ToUpper(), 8.5F, FontStyle.Bold, Muted); e.Location = new Point(0, y); e.Size = new Size(700, 20); page.Controls.Add(e);
                Label h = L(heading, 15, FontStyle.Regular, TextDark); h.Location = new Point(0, y + 23); h.Size = new Size(900, 32); page.Controls.Add(h);
                Label s = L(subtitle, 9, FontStyle.Regular, Muted); s.Location = new Point(0, y + 56); s.Size = new Size(page.Width - 20, 26); page.Controls.Add(s);
            }

            private void BuildChat()
            {
                PageHeading("Tra cứu quy định pháp luật", "Tra cứu quy định pháp luật", "Đặt câu hỏi và xem câu trả lời cùng căn cứ được truy xuất từ tài liệu đã phê duyệt.", 180);
                Panel chat = Card(); chat.Location = new Point(0, 270); chat.Size = new Size(page.Width - 5, 1000); page.Controls.Add(chat);
                Label chatTitle = L("✦  Trợ lý Hỏi đáp Quy chế", 12, FontStyle.Bold, TextDark); chatTitle.Location = new Point(24, 18); chatTitle.Size = new Size(500, 26); chat.Controls.Add(chatTitle);
                Label chatSub = L("Trả lời dựa trên bằng chứng từ tài liệu đã phê duyệt", 9, FontStyle.Regular, Muted); chatSub.Location = new Point(24, 47); chatSub.Size = new Size(600, 22); chat.Controls.Add(chatSub);
                Label rag = L("RAG On-Premise", 9, FontStyle.Bold, Muted); rag.TextAlign = ContentAlignment.MiddleCenter; rag.Location = new Point(chat.Width - 180, 18); rag.Size = new Size(145, 36); chat.Controls.Add(rag);
                Panel separator = new Panel { BackColor = Border, Location = new Point(0, 82), Size = new Size(chat.Width, 1) }; chat.Controls.Add(separator);

                Panel userMsg = new Panel { BackColor = Blue, Location = new Point(chat.Width - 360, 112), Size = new Size(300, 56) };
                Label userText = L("Facebook là gì?", 9.5F, FontStyle.Regular, Color.White); userText.TextAlign = ContentAlignment.MiddleCenter; userText.Dock = DockStyle.Fill; userMsg.Controls.Add(userText); chat.Controls.Add(userMsg);

                Panel refuse = new Panel { BackColor = Color.FromArgb(255, 250, 240), BorderStyle = BorderStyle.FixedSingle, Location = new Point(24, 185), Size = new Size(chat.Width - 430, 160) };
                Label refuseText = L("Tôi chưa tìm thấy đủ bằng chứng từ các tài liệu đã được phê duyệt để trả lời câu hỏi này. Vui lòng thử diễn đạt lại câu hỏi hoặc liên hệ chuyên viên pháp chế.", 9.5F, FontStyle.Regular, TextDark);
                refuseText.Location = new Point(16, 15); refuseText.Size = new Size(refuse.Width - 32, 55); refuse.Controls.Add(refuseText);
                Label gate = L("Cổng bằng chứng từ chối: Không tìm thấy bằng chứng từ tài liệu đã được phê duyệt đạt ngưỡng 0.80. Số vector đang hoạt động: 365.", 8.5F, FontStyle.Regular, Color.FromArgb(145, 102, 37));
                gate.BackColor = Color.FromArgb(255, 239, 202); gate.Location = new Point(16, 78); gate.Size = new Size(refuse.Width - 32, 38); refuse.Controls.Add(gate);
                Label trace = L("TraceId: 3d54938e-1867-4e90-964b-a7e792476e25  ·  Độ tin cậy: 47,6%", 7.5F, FontStyle.Regular, Muted);
                trace.TextAlign = ContentAlignment.MiddleRight; trace.Location = new Point(16, 122); trace.Size = new Size(refuse.Width - 32, 22); refuse.Controls.Add(trace); chat.Controls.Add(refuse);

                Panel userMsg2 = new Panel { BackColor = Blue, Location = new Point(chat.Width - 430, 365), Size = new Size(370, 56) };
                Label userText2 = L("Điều kiện để cấp giấy quyền sử dụng đất là gì?", 9, FontStyle.Regular, Color.White); userText2.TextAlign = ContentAlignment.MiddleCenter; userText2.Dock = DockStyle.Fill; userMsg2.Controls.Add(userText2); chat.Controls.Add(userMsg2);

                Panel answer = new Panel { BackColor = Color.White, BorderStyle = BorderStyle.FixedSingle, Location = new Point(24, 440), Size = new Size(chat.Width - 420, 500) };
                Label answerText = L("Điều kiện để cấp giấy chứng nhận quyền sử dụng đất được quy định tại các Điều 140, 142, 143 và 148 của Bộ Pháp điển - Xây dựng, nhà ở, đô thị.\\r\\n\\r\\nTheo đó, tổ chức, hộ gia đình và cá nhân phải đáp ứng các điều kiện tương ứng về hiện trạng sử dụng đất, nguồn gốc sử dụng đất và giấy tờ chứng minh quyền sử dụng đất.\\r\\n\\r\\n- Tổ chức đang sử dụng đất chưa được cấp Giấy chứng nhận phải tự kê khai hiện trạng và báo cáo cơ quan có thẩm quyền.\\r\\n\\r\\n- Hộ gia đình, cá nhân sử dụng đất cần đối chiếu nguồn gốc sử dụng và các giấy tờ theo quy định.\\r\\n\\r\\n- Đất được giao để thực hiện dự án cần xác định vị trí, diện tích và mục đích sử dụng đất.", 9.5F, FontStyle.Regular, TextDark);
                answerText.Location = new Point(16, 15); answerText.Size = new Size(answer.Width - 32, 280); answer.Controls.Add(answerText);
                Panel citation = new Panel { BackColor = Color.FromArgb(242, 246, 253), Location = new Point(16, 310), Size = new Size(answer.Width - 32, 165), BorderStyle = BorderStyle.FixedSingle };
                Label cTitle = L("Căn cứ trích dẫn", 8.5F, FontStyle.Bold, Muted); cTitle.Location = new Point(12, 8); cTitle.Size = new Size(300, 20); citation.Controls.Add(cTitle);
                Label cDoc = L("Bộ Pháp điển - Xây dựng, nhà ở, đô thị", 9, FontStyle.Bold, TextDark); cDoc.Location = new Point(12, 34); cDoc.Size = new Size(500, 22); citation.Controls.Add(cDoc);
                Label cArticle = L("Điều 142. Cấp Giấy chứng nhận quyền sử dụng đất, quyền sở hữu tài sản", 8.5F, FontStyle.Regular, Muted); cArticle.Location = new Point(12, 59); cArticle.Size = new Size(citation.Width - 24, 22); citation.Controls.Add(cArticle);
                Label cBody = L("Điều 142. Cấp Giấy chứng nhận quyền sử dụng đất, quyền sở hữu tài sản gắn liền với đất cho tổ chức đang sử dụng đất. Tổ chức đang sử dụng đất chưa được cấp Giấy chứng nhận phải tự kê khai hiện trạng sử dụng đất và báo cáo Ủy ban nhân dân cấp tỉnh nơi có đất.", 8.5F, FontStyle.Regular, TextDark);
                cBody.Location = new Point(12, 86); cBody.Size = new Size(citation.Width - 24, 58); citation.Controls.Add(cBody);
                Label cPage = L("Trang 61                                      Độ tương đồng: 85,6%", 8, FontStyle.Regular, Muted); cPage.TextAlign = ContentAlignment.MiddleRight; cPage.Location = new Point(12, 142); cPage.Size = new Size(citation.Width - 24, 18); citation.Controls.Add(cPage);
                answer.Controls.Add(citation); chat.Controls.Add(answer);
            }

            private void BuildDocuments()
            {
                PageHeading("Tiếp nhận và duyệt tài liệu", "Tiếp nhận và duyệt tài liệu", "Tài liệu mới luôn ở trạng thái nháp cho đến khi chuyên viên chủ động phê duyệt.", 180);
                Panel upload = Card(); upload.Location = new Point(0, 270); upload.Size = new Size(page.Width - 5, 460); page.Controls.Add(upload);
                Label eyebrow = L("QUẢN LÝ TRI THỨC", 8.5F, FontStyle.Bold, Muted); eyebrow.Location = new Point(24, 18); eyebrow.Size = new Size(400, 20); upload.Controls.Add(eyebrow);
                Label heading = L("Nạp tài liệu pháp quy", 16, FontStyle.Regular, TextDark); heading.Location = new Point(24, 42); heading.Size = new Size(500, 34); upload.Controls.Add(heading);
                Label desc = L("Tạo hoặc chọn hồ sơ tài liệu, tải PDF/DOCX/HTML lên để trích xuất đoạn văn bản. Phiên bản mới luôn ở trạng thái Draft và chỉ được kích hoạt sau khi một chuyên viên khác phê duyệt.", 9, FontStyle.Regular, Muted);
                desc.Location = new Point(24, 82); desc.Size = new Size(upload.Width - 48, 42); upload.Controls.Add(desc);

                Button createProfile = B("▸  Tạo hồ sơ cho tài liệu mới", Color.FromArgb(249, 251, 254), TextDark);
                createProfile.TextAlign = ContentAlignment.MiddleLeft; createProfile.FlatAppearance.BorderSize = 1; createProfile.FlatAppearance.BorderColor = Border;
                createProfile.Location = new Point(24, 140); createProfile.Size = new Size(upload.Width - 48, 48); upload.Controls.Add(createProfile);

                Label profileLabel = L("Hồ sơ tài liệu", 9, FontStyle.Bold, TextDark); profileLabel.Location = new Point(24, 205); profileLabel.Size = new Size(500, 22); upload.Controls.Add(profileLabel);
                ComboBox profile = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Font = new Font("Segoe UI", 9F), Location = new Point(24, 232), Size = new Size(upload.Width - 48, 38) };
                profile.Items.Add("Bộ Pháp điển - Xây dựng, nhà ở, đô thị · PD_PHAPDIEN"); profile.SelectedIndex = 0; upload.Controls.Add(profile);
                Label format = L("HTML · Xây dựng, nhà ở, đô thị", 8.5F, FontStyle.Regular, Muted); format.Location = new Point(24, 280); format.Size = new Size(500, 22); upload.Controls.Add(format);

                Label versionLabel = L("Số phiên bản", 9, FontStyle.Bold, TextDark); versionLabel.Location = new Point(24, 322); versionLabel.Size = new Size(400, 22); upload.Controls.Add(versionLabel);
                TextBox version = new TextBox { Text = "v1.0", Font = new Font("Segoe UI", 9F, FontStyle.Bold), Location = new Point(24, 350), Size = new Size((upload.Width - 70) / 2, 48), BorderStyle = BorderStyle.FixedSingle };
                upload.Controls.Add(version);
                Panel fileBox = new Panel { Location = new Point(40 + (upload.Width - 70) / 2, 350), Size = new Size((upload.Width - 70) / 2, 68), BorderStyle = BorderStyle.FixedSingle, BackColor = Color.FromArgb(250, 251, 253) };
                Label fileLabel = L("Tệp pháp quy hoặc tài liệu tham khảo\\r\\nChoose File  No file chosen\\r\\nChỉ hỗ trợ PDF, DOCX, HTML và HTM; giới hạn 25 MB.", 8.5F, FontStyle.Regular, Muted);
                fileLabel.Location = new Point(12, 8); fileLabel.Size = new Size(fileBox.Width - 24, 55); fileBox.Controls.Add(fileLabel); upload.Controls.Add(fileBox);
                Button uploadButton = B("Tải lên và xử lý", Color.FromArgb(132, 157, 199), Color.White); uploadButton.Location = new Point(24, 420); uploadButton.Size = new Size(135, 42); upload.Controls.Add(uploadButton);

                Panel versions = Card(); versions.Location = new Point(0, 750); versions.Size = new Size(page.Width - 5, 620); page.Controls.Add(versions);
                Label vEyebrow = L("THEO DÕI VÀ RÀ SOÁT", 8.5F, FontStyle.Bold, Muted); vEyebrow.Location = new Point(24, 18); vEyebrow.Size = new Size(500, 20); versions.Controls.Add(vEyebrow);
                Label vTitle = L("Phiên bản tài liệu", 16, FontStyle.Regular, TextDark); vTitle.Location = new Point(24, 42); vTitle.Size = new Size(500, 32); versions.Controls.Add(vTitle);
                Button refresh = B("Làm mới", Color.White, Blue); refresh.FlatAppearance.BorderSize = 1; refresh.FlatAppearance.BorderColor = Border; refresh.Location = new Point(versions.Width - 120, 18); refresh.Size = new Size(90, 38); versions.Controls.Add(refresh);
                AddVersionCard(versions, "Bộ Pháp điển - Xây dựng, nhà ở, đô thị", "2026 · PB_PHAPDIEN_2026", "PD_PHAPDIEN", "phapdien_housing_land.json", "Không rõ", "Expired", 90);
                AddVersionCard(versions, "Bộ Pháp điển - Xây dựng, nhà ở, đô thị", "v1.0 · PB_DA1F1290", "PD_PHAPDIEN", "31-2024-qh15_1.pdf", "CVPC", "Expired", 265);
                AddVersionCard(versions, "Chế độ sử dụng đất", "v1.0 · PB_CC6C1358", "TLCC15686A3BB44DB88A", "31-2024-qh15_3.pdf", "CVPC", "Approved", 440);
            }

            private void AddVersionCard(Panel parent, string name, string version, string code, string file, string uploader, string status, int y)
            {
                Panel p = new Panel { Location = new Point(24, y), Size = new Size(parent.Width - 48, 155), BorderStyle = BorderStyle.FixedSingle, BackColor = Color.White };
                Label n = L(name, 9, FontStyle.Bold, Muted); n.Location = new Point(18, 12); n.Size = new Size(650, 22); p.Controls.Add(n);
                Label v = L(version, 10, FontStyle.Regular, TextDark); v.Location = new Point(18, 38); v.Size = new Size(650, 24); p.Controls.Add(v);
                Label st = L(status, 8, FontStyle.Bold, status == "Approved" ? Color.FromArgb(44, 139, 105) : Muted); st.TextAlign = ContentAlignment.MiddleCenter; st.BackColor = status == "Approved" ? Color.FromArgb(232, 247, 240) : Color.FromArgb(242, 244, 248); st.Location = new Point(p.Width - 105, 16); st.Size = new Size(78, 28); p.Controls.Add(st);
                Label left = L("Mã tài liệu     " + code + "\\r\\n\\r\\nTệp gốc           " + file, 8.5F, FontStyle.Regular, Muted); left.Location = new Point(18, 76); left.Size = new Size((p.Width - 55) / 2, 62); p.Controls.Add(left);
                Label right = L("Người tải lên     " + uploader + "\\r\\n\\r\\nĐang kích hoạt    " + (status == "Approved" ? "Có" : "Không"), 8.5F, FontStyle.Regular, Muted); right.Location = new Point(p.Width / 2, 76); right.Size = new Size((p.Width - 55) / 2, 62); p.Controls.Add(right);
                parent.Controls.Add(p);
            }

            private void BuildAdmin()
            {
                PageHeading("Trung tâm quản trị", "Trung tâm quản trị", "Theo dõi tài khoản, hoạt động và chất lượng hệ thống.", 180);
                Panel accounts = Card(); accounts.Location = new Point(0, 270); accounts.Size = new Size(page.Width - 5, 490); page.Controls.Add(accounts);
                Label eyebrow = L("QUẢN LÝ DANH TÍNH", 8.5F, FontStyle.Bold, Muted); eyebrow.Location = new Point(24, 18); eyebrow.Size = new Size(500, 20); accounts.Controls.Add(eyebrow);
                Label title = L("Tài khoản người dùng", 16, FontStyle.Regular, TextDark); title.Location = new Point(24, 42); title.Size = new Size(500, 32); accounts.Controls.Add(title);
                Label desc = L("Tạo tài khoản, cập nhật hồ sơ/vai trò hoặc đặt lại mật khẩu. Mật khẩu được băm trước khi lưu.", 9, FontStyle.Regular, Muted); desc.Location = new Point(24, 80); desc.Size = new Size(accounts.Width - 48, 25); accounts.Controls.Add(desc);

                AddInput(accounts, "Tên đăng nhập", "", 24, 120, 400);
                AddInput(accounts, "Họ tên", "", 460, 120, 400);
                AddInput(accounts, "Email", "", 24, 195, 400);
                Label roleLabel = L("Vai trò", 8.5F, FontStyle.Bold, TextDark); roleLabel.Location = new Point(460, 195); roleLabel.Size = new Size(400, 20); accounts.Controls.Add(roleLabel);
                ComboBox roles = new ComboBox { DropDownStyle = ComboBoxStyle.DropDownList, Location = new Point(460, 220), Size = new Size(400, 36), Font = new Font("Segoe UI", 9F) };
                roles.Items.AddRange(new object[] { "Người dùng", "Chuyên viên pháp chế", "Quản trị viên" }); roles.SelectedIndex = 0; accounts.Controls.Add(roles);
                AddInput(accounts, "Mật khẩu", "", 24, 270, 400);
                Button create = B("Tạo tài khoản", Blue, Color.White); create.Location = new Point(24, 345); create.Size = new Size(125, 42); accounts.Controls.Add(create);

                DataGridView users = MakeGrid(); users.Location = new Point(24, 405); users.Size = new Size(accounts.Width - 48, 70);
                users.Columns.Add("id", "Mã"); users.Columns.Add("username", "Tên đăng nhập"); users.Columns.Add("name", "Họ tên"); users.Columns.Add("email", "Email"); users.Columns.Add("role", "Vai trò"); users.Columns.Add("action", "Thao tác");
                users.Rows.Add("ADMIN_01", "admin", "Võ Ngô Minh", "minh@gmail.com", "QuanTriVien", "Sửa   Xóa");
                accounts.Controls.Add(users);

                Panel logs = Card(); logs.Location = new Point(0, 780); logs.Size = new Size(page.Width - 5, 490); page.Controls.Add(logs);
                Label lEyebrow = L("GIÁM SÁT VẬN HÀNH", 8.5F, FontStyle.Bold, Muted); lEyebrow.Location = new Point(24, 18); lEyebrow.Size = new Size(500, 20); logs.Controls.Add(lEyebrow);
                Label lTitle = L("Nhật ký hệ thống", 16, FontStyle.Regular, TextDark); lTitle.Location = new Point(24, 42); lTitle.Size = new Size(500, 32); logs.Controls.Add(lTitle);
                Label lDesc = L("Nhật ký kiểm toán được tải mới nhất trước. Dữ liệu chi tiết được giới hạn theo quyền quản trị viên.", 9, FontStyle.Regular, Muted); lDesc.Location = new Point(24, 80); lDesc.Size = new Size(logs.Width - 48, 25); logs.Controls.Add(lDesc);
                DataGridView logGrid = MakeGrid(); logGrid.Location = new Point(24, 125); logGrid.Size = new Size(logs.Width - 48, 330);
                logGrid.Columns.Add("time", "Thời điểm"); logGrid.Columns.Add("event", "Sự kiện"); logGrid.Columns.Add("user", "Mã người dùng"); logGrid.Columns.Add("status", "Trạng thái"); logGrid.Columns.Add("trace", "Trace");
                logGrid.Rows.Add("2026-11-12T05:14:58Z", "CHAT_RESULT", "USER_DEMO_01", "ThanhCong", "9066a5f5-0072-4e9d");
                logGrid.Rows.Add("2026-11-12T05:14:58Z", "CITATION_BUILT", "USER_DEMO_01", "—", "9066a5f5-0072-4e9d");
                logGrid.Rows.Add("2026-11-12T05:14:58Z", "GENERATION_COMPLETED", "USER_DEMO_01", "—", "9066a5f5-0072-4e9d");
                logGrid.Rows.Add("2026-11-12T05:13:15Z", "EVIDENCE_GATE", "USER_DEMO_01", "—", "3d54938e-1867-4e90");
                logGrid.Rows.Add("2026-11-12T05:13:15Z", "VECTOR_SEARCH", "USER_DEMO_01", "—", "3d54938e-1867-4e90");
                logs.Controls.Add(logGrid);

                Panel evaluation = Card(); evaluation.Location = new Point(0, 1290); evaluation.Size = new Size(page.Width - 5, 520); page.Controls.Add(evaluation);
                Label eEyebrow = L("CHẤT LƯỢNG MÔ HÌNH", 8.5F, FontStyle.Bold, Muted); eEyebrow.Location = new Point(24, 18); eEyebrow.Size = new Size(500, 20); evaluation.Controls.Add(eEyebrow);
                Label eTitle = L("Đánh giá hiệu năng AI", 16, FontStyle.Regular, TextDark); eTitle.Location = new Point(24, 42); eTitle.Size = new Size(500, 32); evaluation.Controls.Add(eTitle);
                Label eDesc = L("Chạy thử truy xuất và tạo câu trả lời trên bộ câu hỏi. Chỉ số chính thức chỉ xuất hiện khi đáp án và nguồn tham chiếu được xác minh pháp lý.", 9, FontStyle.Regular, Muted); eDesc.Location = new Point(24, 80); eDesc.Size = new Size(evaluation.Width - 48, 30); evaluation.Controls.Add(eDesc);
                Button run = B("Chạy đánh giá hiệu năng", Blue, Color.White); run.Location = new Point(24, 120); run.Size = new Size(190, 42); evaluation.Controls.Add(run);
                Button delete = B("Xóa báo cáo mới nhất", Color.White, Blue); delete.FlatAppearance.BorderSize = 1; delete.FlatAppearance.BorderColor = Border; delete.Location = new Point(225, 120); delete.Size = new Size(165, 42); evaluation.Controls.Add(delete);

                int w = (evaluation.Width - 80) / 3;
                AddMetric(evaluation, "50", "Tổng số câu hỏi", "Bộ benchmark hiện tại.", 24, 180, w);
                AddMetric(evaluation, "50/50", "Số câu đã chạy", "48 câu hoàn tất.", 36 + w, 180, w);
                AddMetric(evaluation, "97,9%", "Truy xuất đạt ngưỡng", "47/48 câu hoàn tất có bằng chứng qua ngưỡng.", 48 + w * 2, 180, w);
                AddMetric(evaluation, "47", "Câu trả lời được tạo", "Chỉ số vận hành, không phải câu trả lời đúng.", 24, 305, w);
                AddMetric(evaluation, "1", "Lượt từ chối", "Số lượt hệ thống từ chối.", 36 + w, 305, w);
                AddMetric(evaluation, "2", "Lượt lỗi", "Số lượt xử lý gặp lỗi.", 48 + w * 2, 305, w);
                Label metrics = L("Accuracy: 15,8% (10 mẫu)        Faithfulness: 32,9% (76 mẫu)        Citation Accuracy: 2,0% (50 mẫu)", 9.5F, FontStyle.Bold, Color.FromArgb(166, 112, 28));
                metrics.Location = new Point(24, 440); metrics.Size = new Size(evaluation.Width - 48, 28); evaluation.Controls.Add(metrics);
                Label metricNote = L("Các chỉ số trên là dữ liệu minh họa giao diện, không phải kết quả được tính toán trực tiếp.", 8.5F, FontStyle.Regular, Muted);
                metricNote.Location = new Point(24, 472); metricNote.Size = new Size(evaluation.Width - 48, 22); evaluation.Controls.Add(metricNote);
            }

            private void AddInput(Panel parent, string caption, string value, int x, int y, int width)
            {
                Label label = L(caption, 8.5F, FontStyle.Bold, TextDark); label.Location = new Point(x, y); label.Size = new Size(width, 20); parent.Controls.Add(label);
                TextBox box = new TextBox { Text = value, Font = new Font("Segoe UI", 9F), Location = new Point(x, y + 25), Size = new Size(width, 38), BorderStyle = BorderStyle.FixedSingle };
                parent.Controls.Add(box);
            }

            private DataGridView MakeGrid()
            {
                DataGridView g = new DataGridView();
                g.BackgroundColor = Color.White; g.BorderStyle = BorderStyle.None; g.GridColor = Border;
                g.EnableHeadersVisualStyles = false; g.ColumnHeadersDefaultCellStyle.BackColor = Color.FromArgb(248, 250, 254);
                g.ColumnHeadersDefaultCellStyle.ForeColor = Muted; g.ColumnHeadersDefaultCellStyle.Font = new Font("Segoe UI", 8F, FontStyle.Bold);
                g.DefaultCellStyle.Font = new Font("Segoe UI", 8.5F); g.DefaultCellStyle.ForeColor = TextDark;
                g.DefaultCellStyle.SelectionBackColor = BlueLight; g.DefaultCellStyle.SelectionForeColor = TextDark;
                g.RowHeadersVisible = false; g.AllowUserToAddRows = false; g.ReadOnly = true;
                g.AutoSizeColumnsMode = DataGridViewAutoSizeColumnsMode.Fill; g.RowTemplate.Height = 34;
                g.ColumnHeadersHeight = 34; return g;
            }

            private void AddMetric(Panel parent, string value, string caption, string detail, int x, int y, int width)
            {
                Panel p = new Panel { Location = new Point(x, y), Size = new Size(width, 110), BackColor = Color.FromArgb(251, 252, 255), BorderStyle = BorderStyle.FixedSingle };
                Label v = L(value, 16, FontStyle.Bold, Color.FromArgb(166, 112, 28)); v.Location = new Point(14, 10); v.Size = new Size(width - 28, 26); p.Controls.Add(v);
                Label c = L(caption, 9, FontStyle.Regular, TextDark); c.Location = new Point(14, 40); c.Size = new Size(width - 28, 22); p.Controls.Add(c);
                Label d = L(detail, 7.5F, FontStyle.Regular, Muted); d.Location = new Point(14, 66); d.Size = new Size(width - 28, 36); p.Controls.Add(d);
                parent.Controls.Add(p);
            }
        }
    }
}
