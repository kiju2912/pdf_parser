# PDF Document Clustering & Extraction Tool

**Overview:**  
This project is a comprehensive pipeline for extracting text blocks, table/figure captions, and non-text elements (e.g., images, drawings) from PDF documents. It clusters and merges relevant components, ultimately generating three main outputs:

- **Original PDF**: The untouched document, preserving the initial layout and structure.
- **Processed PDF**: Annotated with colored bounding boxes and labels to highlight detected elements.
- **Extracted PDFs**: Individual PDF files for each captioned or clustered region for close inspection.

---

## Pipeline Overview

1. **Input**  
   - PDF files are placed in the `data/` directory.

2. **Text Extraction & Caption Detection**  
   - Extracts text blocks and uses regular expressions to identify table/figure captions.

3. **Clustering & Region Merging**  
   - Clusters nearby non-text elements (images, drawings) based on spatial proximity. Merges overlapping regions.

4. **Region Extraction**  
   - Saves each caption and cluster region as a separate PDF.

5. **Annotation & Visualization**  
   - Adds bounding boxes and labels in the processed PDF for visual clarity.

6. **Database Storage**  
   - Saves coordinates, labels, and metadata of extracted regions to a MySQL database.

---

## Output Elements

### 1. Original PDF  
Unprocessed version of the PDF.

**Example:**  
![Original PDF](./data/10.pdf)

---

### 2. Processed PDF  
Annotated PDF with detected regions (captions/clusters).

**Example:**  
![Processed PDF](./clustered/10.pdf)

---

### 3. Extracted PDFs  
Each caption or cluster region is exported as an individual file.

**Examples:**  
- ![Figure 1](./output/10/Figure%201_1742227919390704000.pdf)  
- ![Figure 4](./output/10/Figure%204_1742227919422097000.pdf)  
- ![Figure 6](./output/10/Figure%206_1742227919433961000.pdf)  
- ![Table 2](./output/10/Table%202_1742227919294221000.pdf)  
- ![Table 4](./output/10/Table%204_1742227919308019000.pdf)  
- ![Table 6](./output/10/Table%206_1742227919325564000.pdf)

Make sure these paths match your actual file structure.

---

## Installation & Setup

1. **Install Required Libraries**
```
pip install pymupdf mysql-connector-python
```

2. **Configure MySQL Connection**  
Edit the connection settings in your script:
```
mysql.connector.connect(
    host="localhost",
    user="your_username",
    password="your_password",
    database="your_database"
)
```

3. **Project Directory Structure**
```
├── data/                  # Original PDF files  
├── clustered/             # Processed PDFs with annotations  
├── output/                # Extracted individual regions  
├── README.md              # This documentation  
└── c.py                   # Main processing script  
```

4. **Place PDF Files**
- Add the PDF files to the `data/` folder.

5. **Run the Script**
```
python c.py
```

---

## Technical Details

- **Caption Detection**
  - Uses regex to detect "Figure" and "Table" captions.

- **Clustering**
  - Applies BFS/DFS to group nearby images or drawing elements.
  - Merges overlapping clusters into unified bounding boxes.

- **Annotation & Extraction**
  - Adds bounding boxes and labels to processed PDFs.
  - Extracts individual regions and saves them as separate PDFs.

- **Database Integration**
  - Stores metadata like coordinates, captions, and file paths in MySQL.

---

## SQL DB Schema

```
  CREATE TABLE `area` (
 `area_id` int NOT NULL AUTO_INCREMENT,
 `caption_id` int DEFAULT NULL,
 `pdf_file_name` text,
 `png_file_name` text,
 `page_number` int NOT NULL,
 `x0` double DEFAULT NULL,
 `y0` double DEFAULT NULL,
 `x1` double DEFAULT NULL,
 `y1` double DEFAULT NULL,
 `type` enum('figure','table') NOT NULL,
 `appearance_description` text,
 PRIMARY KEY (`area_id`),
 KEY `caption_id` (`caption_id`),
 CONSTRAINT `area_ibfk_1` FOREIGN KEY (`caption_id`) REFERENCES `captions` (`caption_id`) ON DELETE SET NULL
) ENGINE=InnoDB AUTO_INCREMENT=2317 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci

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
) ENGINE=InnoDB AUTO_INCREMENT=5028 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci

CREATE TABLE `pdf_documents` (
 `pdf_id` int NOT NULL AUTO_INCREMENT,
 `file_name` text NOT NULL,
 `processed_date` datetime DEFAULT CURRENT_TIMESTAMP,
 PRIMARY KEY (`pdf_id`)
) ENGINE=InnoDB AUTO_INCREMENT=378 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
```

---

## Conclusion

This tool helps users parse complex PDFs by clustering visual elements and detecting captions without relying on traditional OCR. It offers original, processed, and extracted views, supporting both visual review and structured data storage. The result is a powerful all-in-one solution for PDF-based document analysis.

**For any questions or suggestions, please contact:**  
📧 **kiju2912@naver.com**
