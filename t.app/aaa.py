import ftplib

# FTP 서버 정보
ftp_server = "ftp.example.com"  # FTP 서버 주소
ftp_username = "your_username"  # FTP 사용자 이름
ftp_password = "your_password"  # FTP 비밀번호
ftp_port = 21                   # FTP 포트 (기본값은 21)

# 업로드할 파일 경로
local_file_path = "path/to/your/local_file.py"
remote_file_path = "path/to/remote_directory/remote_file.py"

# FTP 연결 설정 및 파일 업로드
try:
    # FTP 서버에 연결
    ftp = ftplib.FTP()
    ftp.connect(ftp_server, ftp_port)
    ftp.login(ftp_username, ftp_password)
    
    # 바이너리 모드로 파일 열기
    with open(local_file_path, "rb") as file:
        # 파일 업로드
        ftp.storbinary(f"STOR {remote_file_path}", file)
    
    print("파일 업로드 성공")
    
except ftplib.all_errors as e:
    print(f"FTP 오류: {e}")
    
finally:
    # FTP 연결 종료
    ftp.quit()