"""
send_email.py — 发送邮件模块

用法：
    python send_email.py --to liuyuyangxxx@163.com --subject "晨报" --body "内容"
"""

import argparse, json, smtplib, sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header


def send_email(
    to_addr: str,
    subject: str,
    body: str,
    from_addr: str | None = None,
    password: str | None = None,
    smtp_server: str = "smtp.163.com",
    smtp_port: int = 465,
) -> bool:
    """
    通过 SMTP 发送邮件。

    环境变量（优先读取）：
        EMAIL_FROM     — 发件人地址
        EMAIL_PASSWORD — SMTP 密码/授权码
    """

    import os

    from_addr = from_addr or os.environ.get("EMAIL_FROM", "liuyuyangxxx@163.com")
    password   = password   or os.environ.get("EMAIL_PASSWORD", "DEkFgXSgjrSi5ZVZ")

    if not from_addr or not password:
        print("[ERROR] 请设置环境变量 EMAIL_FROM 和 EMAIL_PASSWORD")
        print("  export EMAIL_FROM=yourname@163.com")
        print("  export EMAIL_PASSWORD=your授权码")
        return False

    msg = MIMEMultipart("alternative")
    msg["From"]    = Header(from_addr)
    msg["To"]      = Header(to_addr)
    msg["Subject"] = Header(subject, "utf-8")

    # 纯文本
    msg.attach(MIMEText(body, "plain", "utf-8"))
    # HTML 版（可选）
    html_body = body.replace("\n\n", "<br>").replace("\n", "<br>")
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP_SSL(smtp_server, smtp_port) as server:
            server.login(from_addr, password)
            server.sendmail(from_addr, [to_addr], msg.as_string())
        print(f"[OK] Sent to {to_addr}: {subject}")
        return True
    except Exception as e:
        print(f"[ERROR] Send failed: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="发送邮件")
    parser.add_argument("--to",      required=True, help="收件人")
    parser.add_argument("--subject",  required=True, help="主题")
    parser.add_argument("--body",     required=True, help="正文（支持 @filename 读取文件）")
    args = parser.parse_args()

    body = args.body
    if args.body.startswith("@"):
        with open(args.body[1:], encoding="utf-8") as f:
            body = f.read()

    ok = send_email(args.to, args.subject, body)
    sys.exit(0 if ok else 1)
