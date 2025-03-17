# PDF Parser and Clustering Tool

이 프로젝트는 PDF 문서에서 텍스트 블록, 테이블/피규어 캡션 및 비텍스트 요소(이미지, 드로잉 등)를 추출하여 클러스터링 및 병합하고, 각 영역을 별도의 PDF 파일로 저장하는 파이프라인을 구현합니다. 또한, 추출된 결과(캡션, 테이블 영역, 클러스터 매칭 정보)를 MySQL 데이터베이스에 저장하여 후속 분석이나 활용이 가능하도록 구성되어 있습니다.

---

## 주요 기능

- **텍스트 및 캡션 추출:**  
  PDF에서 텍스트 블록을 추출하고, 정규 표현식을 사용하여 테이블과 피규어 캡션을 식별합니다.

- **비텍스트 요소 클러스터링 및 병합:**  
  이미지 및 드로잉 요소 등 비텍스트 영역을 클러스터링하여 인접하거나 겹치는 영역을 병합합니다.

- **캡션-클러스터 매칭 (DFS 기반):**  
  DFS(깊이 우선 탐색)를 활용하여 캡션과 클러스터 영역을 1:1 매칭합니다.

- **PDF 영역 저장:**  
  추출한 캡션 및 클러스터 영역을 개별 PDF 파일로 저장합니다.

- **MySQL 데이터베이스 저장:**  
  추출된 캡션, 테이블 영역, 클러스터 매칭 정보를 MySQL 데이터베이스에 기록합니다.

---

## 설치 및 요구 사항

- **Python 버전:** 3.6 이상
- **필수 라이브러리:**  
  - [PyMuPDF (fitz)](https://pypi.org/project/PyMuPDF/)  
    ```bash
    pip install pymupdf
    ```
  - [mysql-connector-python](https://pypi.org/project/mysql-connector-python/)  
    ```bash
    pip install mysql-connector-python
    ```
  - 내장 모듈: `os`, `re`, `random`, `math`, `collections`, `datetime`, `time`

---

## 설정

1. **MySQL 데이터베이스 설정:**  
   `save_to_sql` 함수 내에 있는 MySQL 연결 정보(호스트, 사용자, 패스워드, 데이터베이스 이름, 포트)를 실제 환경에 맞게 수정하세요.

2. **입력/출력 디렉터리:**  
   - **입력:** PDF 파일은 기본적으로 `data` 폴더에 위치해야 합니다.
   - **출력:** 처리된 PDF 파일은 `clustered` 폴더에 저장되며, 추출된 영역별 PDF는 `output/<원본 파일명>` 폴더에 저장됩니다.

---

## 사용 방법

1. **라이브러리 설치:**  
   터미널에서 아래 명령어를 실행하여 필요한 라이브러리를 설치합니다.
   ```bash
   pip install pymupdf mysql-connector-python
   ```

2. **MySQL 설정:**  
   코드 내 MySQL 연결 정보를 실제 데이터베이스 정보로 수정합니다.

3. **PDF 파일 준비:**  
   처리할 PDF 파일들을 `data` 폴더에 넣습니다.

4. **프로그램 실행:**  
   터미널에서 아래 명령어를 실행합니다.
   ```bash
   python your_script_name.py
   ```
   여기서 `your_script_name.py`는 본 코드가 저장된 파일 이름입니다.

5. **결과 확인:**  
   - 처리된 PDF 파일은 `clustered` 폴더에 저장됩니다.
   - 추출된 영역별 PDF는 `output/<원본 파일명>` 폴더에서 확인할 수 있습니다.
   - 추출 및 매칭 정보는 MySQL 데이터베이스에 저장됩니다.

---

## 코드 구조 및 주요 알고리즘

- **영역 비교 함수:**  
  - `rect_overlap_ratio`: 두 사각형의 겹치는 면적 비율 계산.
  - `already_drawn`, `is_in_blocks`, `is_intersects_blocks`: 중복 및 교차 여부 판별.

- **클러스터링 및 병합:**  
  - `cluster_elements`: BFS/DFS 방식으로 인접한 비텍스트 요소들을 클러스터링.
  - `merge_overlapping_rects`: 겹치거나 인접한 사각형들을 반복적으로 병합.

- **후보 영역 분리:**  
  - `subtract_rect`: 두 사각형의 교집합을 제거하여 후보 영역 추출.

- **거리 및 점 계산:**  
  - `closest_points_between_rectangles`: 두 사각형 간 최소 거리를 이루는 두 점 계산.

- **캡션-클러스터 매칭 (DFS 기반):**  
  - DFS를 활용하여 각 캡션에 대해 후보 클러스터 목록에서 1:1 매칭을 수행.

- **PDF 저장:**  
  - `save_regions_as_pdf`, `save_cluster_regions_as_pdf`: 캡션 및 클러스터 영역을 개별 PDF 파일로 저장.

- **데이터베이스 저장:**  
  - `save_to_sql`: 처리 결과를 MySQL 데이터베이스에 저장.

- **메인 처리 파이프라인:**  
  - `process_pdf`: 전체 PDF 처리 흐름을 관리.
  - `main`: 지정된 폴더 내 모든 PDF 파일에 대해 처리 실행.

---

## 주의사항 및 개선점

- 복잡한 레이아웃의 PDF 문서에서는 추출 결과가 달라질 수 있습니다.
- 파일 입출력, PDF 파싱, MySQL 연결 등에서 예외 처리 및 로깅 기능 추가가 필요할 수 있습니다.
- 성능 최적화 및 코드 리팩토링을 통해 유지보수를 개선할 수 있습니다.
