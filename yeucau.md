Bối cảnh bài toán
Nhà đầu tư, chuyên viên phân tích và doanh nghiệp tại Việt Nam thường mất nhiều thời gian tra cứu thủ công các chỉ số tài chính (doanh thu, lợi nhuận, ROE, ROA, tỉ lệ nợ/vốn chủ sở hữu, tăng trưởng theo giai đoạn...) nằm rải rác trong hàng trăm báo cáo tài chính (BCTC) dạng bảng của các công ty niêm yết qua nhiều năm. Trợ lý AI Text-to-Pandas được xây dựng nhằm hỗ trợ tự động hoá việc tra cứu, tổng hợp và tính toán các chỉ số này từ dữ liệu BCTC gốc.

Trong bối cảnh trí tuệ nhân tạo phát triển mạnh mẽ, đặc biệt với sự xuất hiện của các mô hình ngôn ngữ lớn như ChatGPT, DeepSeek và Qwen, nhu cầu xây dựng các hệ thống AI có khả năng chuyển đổi câu hỏi ngôn ngữ tự nhiên thành truy vấn dữ liệu bảng (Text-to-Code/Text-to-Pandas) ngày càng trở nên quan trọng. Tuy nhiên, so với các bài toán Text-to-SQL trên dữ liệu tiếng Anh, nguồn tài nguyên và nghiên cứu về Text-to-Pandas trên dữ liệu tài chính tiếng Việt vẫn còn hạn chế.

Nhằm thúc đẩy nghiên cứu và phát triển trong lĩnh vực này, chúng tôi tổ chức cuộc thi về Truy hồi Bảng dữ liệu & Sinh truy vấn Pandas trên Báo cáo tài chính doanh nghiệp niêm yết (Financial Table Retrieval & Text-to-Pandas Query Generation). Cuộc thi hướng tới việc xây dựng các hệ thống AI có khả năng xác định đúng bảng dữ liệu liên quan và tự động sinh, thực thi câu lệnh pandas để trả lời chính xác câu hỏi về chỉ số tài chính.

Truy hồi bảng dữ liệu (Table Retrieval) là nhiệm vụ cốt lõi đầu tiên, liên quan đến việc xác định bảng dữ liệu nào phù hợp nhất với một truy vấn cho trước. Nhiệm vụ có thể được hình thức hoá như sau: Cho một tập câu hỏi Q = {q1, q2, ..., qn} và một kho báo cáo tài chính D = {d1, d2, ..., dn} (mỗi báo cáo gồm nhiều bảng: Bảng cân đối kế toán, Báo cáo kết quả kinh doanh, Báo cáo lưu chuyển tiền tệ, thuyết minh), nhiệm vụ yêu cầu xác định một tập con bảng D′ ⊂ D trong đó mỗi bảng di ∈ D′ được coi là "liên quan" đến câu hỏi tương ứng q. Chúng tôi gọi một bảng dữ liệu là "Liên quan" nếu bảng đó chứa (một phần hoặc toàn bộ) số liệu cần thiết để tính ra câu trả lời.

Sinh truy vấn Pandas (Text-to-Pandas) dựa trên các bảng đã truy hồi, hệ thống cần sinh ra câu lệnh pandas thực thi được để tính toán và trả về đúng số liệu cho câu hỏi tài chính tương ứng. Mục tiêu của nhiệm vụ là xây dựng các hệ thống AI có khả năng không chỉ tìm đúng bảng dữ liệu căn cứ mà còn hiểu và chuyển hoá đúng logic tính toán tài chính thành code, đảm bảo kết quả có thể kiểm chứng và tái lập.

Mục tiêu cuộc thi
Các đội thi cần xây dựng hệ thống AI có khả năng:

1. Truy hồi dữ liệu chính xác
Xác định đúng công ty, đúng năm, đúng bảng dữ liệu chứa số liệu cần thiết.
Tìm kiếm và truy xuất chính xác vị trí bảng dữ liệu từ kho BCTC được cung cấp.
Ưu tiên khả năng retrieval và grounding chính xác trên dữ liệu dạng bảng.
2. Hiểu truy vấn tài chính bằng tiếng Việt
Hiểu ngôn ngữ tự nhiên tiếng Việt về các chỉ số và thuật ngữ tài chính.
Xử lý được câu hỏi so sánh nhiều công ty, nhiều năm, hoặc chỉ số dẫn xuất (ROE, ROA, tăng trưởng...).
3. Sinh truy vấn pandas & tính toán chính xác
Sinh câu lệnh pandas chạy được, đúng logic, đúng schema dữ liệu.
Trả về đúng số liệu, đúng đơn vị, đúng kỳ báo cáo được hỏi.
4. Dẫn nguồn minh bạch
Trích dẫn công ty, năm, tên báo cáo, tên bảng và vị trí (trang/mục) chứa số liệu gốc.
Hiển thị rõ nguồn tham chiếu để đảm bảo khả năng kiểm chứng thông tin.
Hạn chế việc trả lời không có căn cứ dữ liệu.
5. Kiểm soát nội dung sai lệch
Hạn chế việc AI sinh ra số liệu sai lệch (hallucination).
Tránh bịa bảng dữ liệu hoặc nguồn tham chiếu không tồn tại.
Tăng độ tin cậy của câu trả lời dựa trên dữ liệu được cung cấp.
Các mốc thời gian quan trọng
01 tháng 8, 2026: Mở hệ thống nộp bài cho tập kiểm thử công khai (public test)
31 tháng 8, 2026: Hạn chót nộp bài cho tập kiểm thử công khai
01 tháng 9, 2026: Mở hệ thống nộp bài cho tập kiểm thử riêng (private test)
03 tháng 9, 2026: Hạn chót nộp bài cho tập kiểm thử riêng
06 tháng 9, 2026: Công bố kết quả chung cuộc
Lưu ý: Tất cả các hạn chót đều là 23:59 theo giờ Việt Nam (UTC+07:00).

Quy định về dữ liệu bên ngoài và mô hình ngôn ngữ huấn luyện trước (PLMs)
Người tham gia được phép sử dụng dữ liệu từ các nguồn bên ngoài, tuy nhiên phải trích dẫn rõ ràng và cung cấp đầy đủ thông tin về nguồn gốc dữ liệu để Ban tổ chức có thể kiểm tra, xác minh khi cần thiết. Bạn có thể sử dụng các mô hình ngôn ngữ huấn luyện trước và các LLM có dữ liệu huấn luyện và/hoặc mô hình được công khai (ví dụ: Hugging Face hoặc các trang tương tự), nhưng bạn không được sử dụng các LLM có mô hình đóng (ví dụ: GPT-4o, Gemini, ...). Ngoài ra, bạn chỉ được sử dụng các mô hình được phát hành trước ngày 1 tháng 6 năm 2026 (giờ Việt Nam) có kích thước nhỏ hơn hoặc bằng 14B. Vì mục đích tái lập kết quả, vui lòng đưa thông tin về cách thức lấy mô hình vào bài báo.

Phương pháp đánh giá
Hiệu năng của hệ thống được đánh giá bằng ba tiêu chí tự động: Truy hồi thông tin, Độ chính xác kết quả, và Độ chính xác pandas query. Chúng tôi sử dụng trung bình macro (chỉ số đánh giá được tính cho từng truy vấn rồi lấy trung bình) để tính điểm đánh giá cuối cùng.

3.1 Truy hồi thông tin
Hiệu suất hệ thống trên nhiệm vụ truy hồi bảng dữ liệu được đánh giá bằng các chỉ số Độ chính xác (Precision), Độ bao phủ (Recall) và điểm F2 macro. Chúng tôi sử dụng macro-average (tính chỉ số đánh giá cho từng truy vấn rồi lấy trung bình) để tính điểm đánh giá cuối cùng.

Độ chính xác (Precision): Precision = trung bình của (số bảng dữ liệu truy hồi đúng cho mỗi truy vấn) / (số bảng dữ liệu đã truy hồi cho mỗi truy vấn)
Độ bao phủ (Recall): Recall = trung bình của (số bảng dữ liệu truy hồi đúng cho mỗi truy vấn) / (số bảng dữ liệu liên quan của mỗi truy vấn)
Độ đo F2: F2 = (5 × Precision × Recall) / (4 × Precision + Recall)
3.2 Độ chính xác kết quả
Độ chính xác của số liệu đầu ra so với đáp án chuẩn, tính trong ngưỡng sai số cho phép do Ban Tổ chức (BTC) công bố.

Answer Accuracy = (số query có kết quả khớp đáp án chuẩn, trong ngưỡng sai số) / (tổng số query)
3.3 Độ chính xác pandas query
Hiệu suất hệ thống trên nhiệm vụ sinh mã truy vấn và tính toán trên bảng dữ liệu tài chính được đánh giá bằng chỉ số Execution Accuracy. Chúng tôi sử dụng macro-average để tính điểm đánh giá cuối cùng.

Execution Accuracy = (số code chạy được và cho kết quả đúng) / (tổng số query)


Dashboard kết quả
Các đội thi nộp kết quả dự đoán trực tiếp trên hệ thống Dashboard chính thức của cuộc thi. Mỗi lần nộp bài cần đảm bảo các yêu cầu sau:

Định dạng file: kết quả được nộp dưới dạng file chuẩn theo mẫu do Ban Tổ chức quy định, với cấu trúc trường dữ liệu tuân thủ đúng đặc tả.
Nội dung file: bao gồm kết quả dự đoán cho toàn bộ câu hỏi trong bộ dữ liệu kiểm thử. Các câu hỏi bị thiếu hoặc sai định dạng sẽ bị tính là dự đoán không hợp lệ.
Số lần nộp: mỗi đội được giới hạn số lần nộp bài mỗi ngày (chi tiết sẽ được công bố trên Dashboard) nhằm đảm bảo tính công bằng và tránh hiện tượng dò đáp án.
Định dạng nộp bài
Bạn phải nộp một file dự đoán duy nhất ở định dạng .json. File phải tuân theo cấu trúc sau:

[
  {
    "id": <integer>,
    "question": "<string>",
    "answer": <float>,
    "relevant_docs": ["<id_báo_cáo>"],
    "relevant_tables": ["<id_báo_cáo>|<vị trí trong báo cáo>"],
    "evidence": [
      {
        "variable": "<tên_biến_dataframe>",
        "csv_path": "<string>"
      }
    ],
    "pandas_query": "<string>"
  },
  ...
]
Giải thích:

id: Mã định danh của câu hỏi, kiểu số nguyên (integer).
question: Nội dung câu hỏi tài chính, kiểu chuỗi (string).
relevant_docs: Danh sách mã định danh của các báo cáo hoặc tài liệu có liên quan đến câu hỏi. Mã báo cáo được xác định từ tên file cuối cùng trong đường dẫn tài liệu và loại bỏ phần mở rộng .txt. Ví dụ, với đường dẫn: ocr_filter\AAA\2015\AAA_financial_statements_2015_consolidated thì mã báo cáo được sử dụng là: AAA_financial_statements_2015_consolidated.
relevant_tables: Danh sách các bảng dữ liệu có liên quan trực tiếp đến câu trả lời. Mỗi phần tử có định dạng <id_báo_cáo>|<vị trí bảng trong báo cáo>, trong đó:
id_báo_cáo: Tên file cuối cùng trong đường dẫn tài liệu sau khi loại bỏ phần mở rộng .txt.
vị trí bảng trong báo cáo: Vị trí hoặc số thứ tự của bảng trong báo cáo theo dữ liệu do Ban Tổ chức cung cấp.
Ví dụ: AAA_financial_statements_2015_consolidated|350.
answer: Kết quả số liệu kiểu số thực (float).
evidence: Danh sách các bảng dữ liệu được sử dụng để thực thi pandas_query. Mỗi phần tử gồm:
variable: Tên biến DataFrame đại diện cho bảng và được sử dụng trực tiếp trong pandas_query. Tên biến phải hợp lệ trong Python và không được trùng nhau trong cùng một câu hỏi.
csv_path: Đường dẫn tương đối tới file CSV chứa dữ liệu mà pandas_query đã sử dụng để tính ra answer. Đường dẫn phải nằm trong thư mục data/ của gói nộp bài.
pandas_query: Câu lệnh pandas được sinh ra để trích xuất/tính toán ra đáp án, kiểu chuỗi (string), có thể chạy lại được trên dữ liệu đã chuẩn hoá.
Ví dụ bài nộp:

[
  {
    "id": 1,
    "question": "Doanh thu thuần của Công ty CP Sữa Việt Nam (VNM) năm 2023 là bao nhiêu?",
    "answer": 63075000000,
    "relevant_docs": ["AAA_financial_statements_2015_consolidated"],
    "relevant_tables": ["AAA_financial_statements_2015_consolidated|350"],
    "evidence": [
      {
        "variable": "df1",
        "csv_path": "data/AAA_financial_statements_2015_consolidated_table_1.csv"
      }
    ],
    "pandas_query": "df1[(df1.company=='VNM') & (df1.year==2023)]['net_revenue'].values[0]",
  }
]
Bài nộp phải được đóng gói dưới dạng một file ZIP, bao gồm một file kết quả .json và thư mục data/ chứa đầy đủ các file CSV được tham chiếu bởi csv_path trong file kết quả.

Cấu trúc file ZIP:

submission.zip
├── submission.json
└── data/
    ├── <bảng_1>.csv
    ├── <bảng_2>.csv
    └── ...
Sau đó, vào mục My Submissions trên http://leaderboard.aiguru.com.vn/ và tải lên file ZIP.

Lưu ý:

File .json và thư mục data/ phải nằm trực tiếp ở cấp ngoài cùng của file ZIP, không được đặt trong một thư mục cha khác.
File ZIP chỉ được chứa một file kết quả .json.
Mọi csv_path, bao gồm csv_path trong evidence, phải là đường dẫn tương đối bắt đầu bằng data/.
Xin lưu ý rằng các bài nộp bị thiếu file hoặc thiếu câu sẽ không được đánh giá và sẽ không bị tính vào số lần nộp tối đa cho phép.
Quy định nộp bài
Mỗi đội được phép nộp tối đa 10 bài mỗi ngày.
Số bài nộp tối đa cho mỗi người dùng trong Vòng riêng (Private Phase) là 5 bài tổng cộng. Vì vậy, hãy chọn lựa các bài nộp ở Vòng riêng một cách cẩn thận.
Vui lòng chọn một tên người dùng đại diện cho đội của bạn.
Kết quả cuối cùng sẽ không được xem là chính thức cho đến khi một bài báo mô tả phương pháp (working notes paper) với mô tả đầy đủ về các phương pháp được nộp.
Ban Tổ chức Cuộc thi có toàn quyền, theo quyết định riêng của mình, loại bất kỳ thí sinh nào có bài nộp không tuân thủ tất cả các yêu cầu.

Dữ liệu cuộc thi
Nguồn dữ liệu chính thức của cuộc thi:
Bạn có thể truy cập và tải toàn bộ Dataset trên HuggingFace tại đây:
Truy cập HuggingFace Dataset (ViFinQA)
Ban Tổ chức cung cấp:

Kho dữ liệu báo cáo tài chính: BCTC của 100 công ty niêm yết trong 10 năm (Bảng cân đối kế toán, Báo cáo kết quả kinh doanh, Báo cáo lưu chuyển tiền tệ, thuyết minh BCTC), làm nguồn dữ liệu gốc để truy hồi và tính toán.
Bộ dữ liệu kiểm thử (test set): tập câu hỏi về chỉ số tài chính, được sử dụng làm căn cứ chấm điểm và đánh giá hệ thống của các đội thi. Không cung cấp bất kỳ tập dữ liệu huấn luyện (train) hay tập phát triển (dev) nào.
Bộ đáp án chuẩn: được Ban Tổ chức giữ kín, chỉ phục vụ quá trình chấm điểm nhằm đảm bảo tính khách quan và công bằng.

Ban Tổ chức không cung cấp pipeline xử lý/chuẩn hoá dữ liệu sẵn có. Các đội thi được toàn quyền chủ động trong việc trích xuất, làm sạch và cấu trúc hoá dữ liệu, bao gồm:

Trích xuất bảng dữ liệu từ file do BTC cung cấp.
Xây dựng schema chuẩn hoá (tên công ty, năm, tên bảng, tên cột, đơn vị tính).
Các tập dữ liệu mở (open dataset) khác về tài chính doanh nghiệp niêm yết Việt Nam.
Mọi nguồn dữ liệu hợp pháp khác mà đội thi có thể tiếp cận.
Cuộc thi khuyến khích các đội phát huy tối đa sự sáng tạo trong toàn bộ quy trình xây dựng giải pháp, chẳng hạn:

Tiền xử lý dữ liệu bảng từ BCTC.
Thiết kế chiến lược biểu diễn dữ liệu và schema linking (ánh xạ câu hỏi ↔ tên bảng/cột).
Tối ưu hoá cơ chế truy hồi bảng dữ liệu liên quan.
Xây dựng pipeline sinh, kiểm tra và tự sửa lỗi câu lệnh pandas.
Kho báo cáo tài chính
Ban Tổ chức cung cấp kho báo cáo tài chính dưới dạng các file văn bản có phần mở rộng .txt. Mỗi file chứa nội dung của một báo cáo tài chính, bao gồm các thông tin thuyết minh và các bảng số liệu liên quan.

Mỗi đội thi có nhiệm vụ khai thác dữ liệu từ các file .txt để truy hồi thông tin và tính toán đáp án cho bộ câu hỏi kiểm thử. Các đội được chủ động lựa chọn phương pháp nhận diện bảng, trích xuất, làm sạch, chuẩn hóa và cấu trúc hóa dữ liệu phù hợp với giải pháp của mình.

Bộ câu hỏi kiểm thử
Mỗi câu hỏi trong bộ dữ liệu kiểm thử bao gồm:

id: Mã định danh của câu hỏi, kiểu số nguyên (integer).
question: Nội dung câu hỏi tài chính, kiểu chuỗi (string).
{
  "id": <integer>,
  "question": "<string>"
}
Ví dụ dữ liệu:

{
  "id": 1,
  "question": "Doanh thu thuần của Công ty CP Sữa Việt Nam (VNM) năm 2023 là bao nhiêu VNĐ?"
}


Quy định chung
Quyền hủy bỏ, sửa đổi hoặc loại tư cách. Ban Tổ chức Cuộc thi có toàn quyền theo quyết định riêng của mình để chấm dứt, sửa đổi hoặc tạm ngưng cuộc thi.
Khi nộp kết quả cho cuộc thi này, bạn đồng ý cho phép công bố công khai điểm số của mình tại hội thảo của Cuộc thi và trong các kỷ yếu liên quan, theo quyết định của ban tổ chức nhiệm vụ. Điểm số có thể bao gồm nhưng không giới hạn ở các đánh giá định lượng tự động và thủ công, các đánh giá định tính, cùng các chỉ số khác mà ban tổ chức nhiệm vụ cho là phù hợp. Bạn chấp nhận rằng quyết định cuối cùng về việc lựa chọn chỉ số và giá trị điểm số thuộc về ban tổ chức nhiệm vụ.
Khi tham gia cuộc thi, bạn đã chấp nhận các điều khoản và điều kiện của Điều khoản Tham gia và Thỏa thuận Sử dụng Dữ liệu của Nhiệm vụ chung R2AI2026 TEXT-TO-PANDAS, đã được gửi đến email của bạn.
Khi tham gia cuộc thi, bạn khẳng định và thừa nhận rằng bạn đồng ý tuân thủ các luật và quy định hiện hành, và bạn không được xâm phạm bất kỳ bản quyền, tài sản trí tuệ hoặc bằng sáng chế nào của bên khác đối với phần mềm bạn phát triển trong quá trình diễn ra cuộc thi, và sẽ không vi phạm bất kỳ luật và quy định hiện hành nào liên quan đến kiểm soát xuất khẩu cũng như quyền riêng tư và bảo vệ dữ liệu.
Giải thưởng phụ thuộc vào việc Ban Tổ chức Cuộc thi xem xét và xác minh tư cách hợp lệ của thí sinh cũng như sự tuân thủ các quy định này, cùng với sự tuân thủ của các bài nộp thắng giải đối với các yêu cầu nộp bài.
Người tham gia trao cho Ban Tổ chức Cuộc thi quyền sử dụng các bài nộp thắng giải cùng mã nguồn và dữ liệu được tạo ra cho và dùng để tạo ra bài nộp đó vì bất kỳ mục đích nào và không cần phê duyệt thêm.
Điều kiện tham gia
Mỗi người tham gia phải tạo một tài khoản để nộp giải pháp cho cuộc thi. Chỉ cho phép một tài khoản cho mỗi người dùng.
Cuộc thi là công khai, nhưng Ban Tổ chức Cuộc thi có thể quyết định không cho phép tham gia theo cân nhắc riêng của mình.
Ban Tổ chức Cuộc thi có quyền loại bất kỳ thí sinh nào khỏi cuộc thi nếu, theo quyết định riêng của Ban Tổ chức, họ có cơ sở hợp lý để tin rằng thí sinh đã cố gắng làm suy yếu hoạt động hợp pháp của cuộc thi thông qua gian lận, lừa dối hoặc các hành vi chơi không công bằng khác.
Đội thi
Người tham gia được phép lập đội.
Bạn không được tham gia nhiều hơn một đội. Mỗi thành viên trong đội phải là một cá nhân riêng biệt vận hành một tài khoản riêng.
Chỉ một tài khoản cho mỗi đội được phê duyệt để nộp kết quả.