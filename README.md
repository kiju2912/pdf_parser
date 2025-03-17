# PDF Document Clustering & Extraction Tool

**Overview:**  
이 프로젝트는 PDF 문서에서 텍스트 블록, 테이블/피규어 캡션 및 비텍스트 요소(이미지, 드로잉 등)를 추출하여 클러스터링 및 병합하는 종합 파이프라인입니다. 최종적으로는 세 가지 주요 산출물을 생성합니다:

- **원본 PDF**: 처리 전의 원본 문서로, 문서의 초기 상태를 확인할 수 있습니다.
- **처리된 PDF**: 캡션 및 클러스터 영역이 색상과 레이블로 주석 처리되어, 문서 내 어떤 요소가 검출되었는지 한눈에 파악할 수 있습니다.
- **추출된 PDF**: 각 캡션 및 클러스터 영역을 별도의 PDF 파일로 저장하여, 세부 내용을 집중적으로 검토할 수 있습니다.

---

## Pipeline Overview

1. **입력**  
   - 원본 PDF 파일은 `data/` 디렉터리에 배치됩니다.
2. **텍스트 추출 & 캡션 검출**  
   - PDF 내 텍스트 블록을 추출하고, 정규 표현식을 사용하여 테이블/피규어 캡션을 식별합니다.
3. **클러스터링 & 영역 병합**  
   - 이미지 및 드로잉과 같은 비텍스트 요소를 인접도 기반으로 클러스터링하고, 겹치는 영역은 병합합니다.
4. **영역 추출**  
   - 캡션과 클러스터 영역을 개별 PDF 파일로 저장합니다.
5. **주석 처리 및 시각화**  
   - 처리된 PDF에 검출된 영역에 대해 경계 상자와 레이블을 삽입해 시각적으로 확인합니다.
6. **데이터베이스 저장**  
   - 추출된 영역의 좌표, 텍스트 및 기타 메타데이터를 MySQL 데이터베이스에 기록합니다.

---

## Output Elements

### 1. 원본 PDF  
**설명:**  
원본 PDF는 처리 전의 문서 상태를 그대로 보여줍니다. 문서의 레이아웃과 콘텐츠를 변경 없이 확인할 수 있습니다.

**예시:**  
![원본 PDF](./data/10.pdf)  
*예시: 원본 PDF 문서*

---

### 2. 처리된 PDF  
**설명:**  
처리된 PDF는 캡션 및 클러스터 영역이 색상과 레이블로 주석 처리되어 있습니다. 이 파일을 통해 어떤 영역이 추출 대상이었는지 시각적으로 확인할 수 있습니다.

**예시:**  
![처리된 PDF](./clustered/10.pdf)  
*예시: 주석이 추가된 처리된 PDF (예: 경계 상자 및 레이블 표시)*

---

### 3. 추출된 PDF  
**설명:**  
각 캡션이나 클러스터 영역을 별도의 PDF 파일로 저장하여, 세부 내용을 집중적으로 검토할 수 있습니다.

**예시:**  
- **Figure 1 추출:**  
  ![Figure 1](./output/10/Figure%201_1742227919390704000.pdf)  
  *예시: Figure 1 영역 추출 결과*
- **Figure 4 추출:**  
  ![Figure 4](./output/10/Figure%204_1742227919422097000.pdf)  
  *예시: Figure 4 영역 추출 결과*
- **Figure 6 추출:**  
  ![Figure 6](./output/10/Figure%206_1742227919433961000.pdf)  
  *예시: Figure 6 영역 추출 결과*
- **Table 2 추출:**  
  ![Table 2](./output/10/Table%202_1742227919294221000.pdf)  
  *예시: Table 2 영역 추출 결과*
- **Table 4 추출:**  
  ![Table 4](./output/10/Table%204_1742227919308019000.pdf)  
  *예시: Table 4 영역 추출 결과*
- **Table 6 추출:**  
  ![Table 6](./output/10/Table%206_1742227919325564000.pdf)  
  *예시: Table 6 영역 추출 결과*

*주의: 위 이미지 경로는 각 파일이 `data/`, `clustered/`, `output/` 디렉터리에 저장되었음을 전제로 합니다. 실제 경로에 맞게 수정하세요.*

---

## Installation & Setup

1. **필수 라이브러리 설치:**  
   ```bash
   pip install pymupdf mysql-connector-python
   ```

2. **MySQL 데이터베이스 설정:**  
   - `save_to_sql` 함수 내의 MySQL 연결 정보를 실제 환경에 맞게 수정합니다.

3. **디렉터리 구조:**  
   ```
   ├── data/                  # 원본 PDF 파일
   ├── clustered/             # 처리된 PDF (주석 포함)
   ├── output/                # 추출된 개별 PDF 영역
   ├── README.md              # 이 파일
   └── your_script_name.py    # 메인 처리 스크립트
   ```

4. **PDF 파일 배치:**  
   - 분석할 PDF 파일들을 `data/` 폴더에 넣습니다.

5. **프로그램 실행:**  
   ```bash
   python your_script_name.py
   ```

---

## Technical Details

- **텍스트 & 캡션 검출:**  
  - 정규 표현식을 통해 테이블과 피규어 캡션을 식별합니다.
  - 텍스트 블록을 분리하여 주요 콘텐츠와 캡션을 구분합니다.

- **클러스터링 알고리즘:**  
  - 인접한 비텍스트 요소(이미지, 드로잉)를 BFS/DFS 방식으로 클러스터링합니다.
  - 겹치는 영역은 반복적으로 병합하여 최종 클러스터를 생성합니다.

- **영역 추출 및 주석 처리:**  
  - 처리된 PDF에 경계 상자와 텍스트 레이블을 추가해, 각 영역의 역할과 위치를 명확히 합니다.
  - 각 캡션 및 클러스터 영역을 별도의 PDF 파일로 저장합니다.

- **데이터베이스 저장:**  
  - 추출 결과(좌표, 텍스트 등)를 MySQL 데이터베이스에 기록하여, 후속 분석 및 통합이 가능하도록 합니다.

---

## Conclusion

이 도구는 PDF 문서의 복잡한 레이아웃을 효과적으로 분석하여, 원본 문서, 처리된 결과, 그리고 추출된 영역들을 제공함으로써 사용자가 문서 내 중요한 정보를 한눈에 파악할 수 있도록 도와줍니다. 시각적 주석 처리와 개별 영역 추출 기능을 통해 문서 분석 및 데이터베이스 연동까지 지원하는 올인원 솔루션입니다.

문의 사항이나 제안은 kiju2912@naver.com으로 부탁드립니다.

---

## sql db
 ```bash
   
CREATE TABLE `captions` (
  `caption_id` int NOT NULL AUTO_INCREMENT,
  `caption_name` text,
  `pdf_id` int NOT NULL,
  `page_number` int NOT NULL,
  `caption_text` text,
  `x0` double DEFAULT NULL,
  `y0` double DEFAULT NULL,
  `x1` double DEFAULT NULL,
  `y1` double DEFAULT NULL,
  PRIMARY KEY (`caption_id`),
  KEY `pdf_id` (`pdf_id`),
  CONSTRAINT `captions_ibfk_1` FOREIGN KEY (`pdf_id`) REFERENCES `pdf_documents` (`pdf_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=1729 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci  CREATE TABLE `clusters` (
  `cluster_id` int NOT NULL AUTO_INCREMENT,
  `caption_id` int DEFAULT NULL,
  `page_number` int NOT NULL,
  `pdf_file_name` text,
  `x0` double DEFAULT NULL,
  `y0` double DEFAULT NULL,
  `x1` double DEFAULT NULL,
  `y1` double DEFAULT NULL,
  PRIMARY KEY (`cluster_id`),
  KEY `caption_id` (`caption_id`),
  CONSTRAINT `clusters_ibfk_1` FOREIGN KEY (`caption_id`) REFERENCES `captions` (`caption_id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=931 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci  CREATE TABLE `pdf_documents` (
  `pdf_id` int NOT NULL AUTO_INCREMENT,
  `file_name` text NOT NULL,
  `processed_date` datetime DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (`pdf_id`)
) ENGINE=InnoDB AUTO_INCREMENT=125 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci  CREATE TABLE `tables` (
  `table_region_id` int NOT NULL AUTO_INCREMENT,
  `caption_id` int NOT NULL,
  `pdf_file_name` text,
  `page_number` int NOT NULL,
  `x0` double DEFAULT NULL,
  `y0` double DEFAULT NULL,
  `x1` double DEFAULT NULL,
  `y1` double DEFAULT NULL,
  PRIMARY KEY (`table_region_id`),
  KEY `caption_id` (`caption_id`),
  CONSTRAINT `tables_ibfk_1` FOREIGN KEY (`caption_id`) REFERENCES `captions` (`caption_id`) ON DELETE CASCADE
) ENGINE=InnoDB AUTO_INCREMENT=764 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
```
