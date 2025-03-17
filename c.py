import os
import re
import random
import fitz  # PyMuPDF
import math
from collections import deque
import mysql.connector
from datetime import datetime
import time

GROUP_TOLERANCE = 10

def rect_overlap_ratio(r1, r2):
    # 두 사각형의 겹치는 면적을 계산하고, 더 작은 사각형 면적 대비 비율을 반환
    x0 = max(r1.x0, r2.x0)
    y0 = max(r1.y0, r2.y0)
    x1 = min(r1.x1, r2.x1)
    y1 = min(r1.y1, r2.y1)
    if x1 > x0 and y1 > y0:
        inter_area = (x1 - x0) * (y1 - y0)
        return inter_area / min(r1.get_area(), r2.get_area())
    return 0

def already_drawn(page_number, rect, drawn_list, threshold=0.8):
    # drawn_list에 있는 사각형 중 겹침률이 threshold 이상이면 이미 그린 것으로 판단
    for pn, r in drawn_list:
        if page_number == pn and rect_overlap_ratio(rect, r) > threshold:
            return True
    return False

def is_in_blocks(page_number, rect, drawn_list):
    for tup in drawn_list:
        pn, r = tup[0], tup[1]
        if page_number == pn and (r.contains(rect) or r.intersects(rect)):
            return True
    return False

def is_intersects_blocks(page_number, rect, drawn_list):
    for tup in drawn_list:
        pn, r = tup[0], tup[1]
        if page_number == pn and r.intersects(rect):
            return True
    return False

def is_near(r1, r2, threshold):
    """두 사각형이 threshold 이내에 있는지 판단"""
    dx = max(r1.x0 - r2.x1, r2.x0 - r1.x1, 0)
    dy = max(r1.y0 - r2.y1, r2.y0 - r1.y1, 0)
    return (dx**2 + dy**2)**0.5 <= threshold

def cluster_elements(rects, threshold=5):
    """비텍스트 요소들의 사각형 리스트를 threshold 기준으로 클러스터링"""
    clusters = []
    visited = set()
    for i, rect in enumerate(rects):
        if i in visited:
            continue
        cluster = []
        queue = deque([i])
        while queue:
            idx = queue.popleft()
            if idx in visited:
                continue
            visited.add(idx)
            cluster.append(rects[idx])
            for j, other in enumerate(rects):
                if j not in visited and is_near(rects[idx], other, threshold):
                    queue.append(j)
        clusters.append(cluster)
    return clusters

def merge_overlapping_rects(rects, tol=0):
    """
    입력된 사각형 목록 중 서로 겹치거나 인접(tol 이하 차이)하는 사각형들을 반복적으로 합칩니다.
    """
    if not rects:
        return []
    merged = rects.copy()
    changed = True
    while changed:
        changed = False
        new_merged = []
        while merged:
            current = merged.pop(0)
            i = 0
            while i < len(merged):
                if current.intersects(merged[i]) or current.contains(merged[i]) or merged[i].contains(current):
                    current |= merged.pop(i)
                    changed = True
                else:
                    i += 1
            new_merged.append(current)
        merged = new_merged
    return merged

def subtract_rect(original, subtract):
    """
    original 사각형에서 subtract 사각형과의 교집합 영역을 제외한 후보 영역들을 반환합니다.
    (상, 하, 좌, 우 영역을 후보로 추출)
    """
    if not original.intersects(subtract):
        return [original]
    inter = original & subtract  # 교집합 영역
    candidates = []
    if inter.y0 > original.y0:
        candidates.append(fitz.Rect(original.x0, original.y0, original.x1, inter.y0))
    if inter.y1 < original.y1:
        candidates.append(fitz.Rect(original.x0, inter.y1, original.x1, original.y1))
    if inter.x0 > original.x0:
        candidates.append(fitz.Rect(original.x0, inter.y0, inter.x0, inter.y1))
    if inter.x1 < original.x1:
        candidates.append(fitz.Rect(inter.x1, inter.y0, original.x1, inter.y1))
    return [c for c in candidates if c.get_area() > 0]

def closest_points_between_rectangles(r1, r2):
    """
    두 fitz.Rect 객체 r1, r2에 대해 각 사각형의 경계상에서
    서로 간의 최소 거리를 이루는 두 점을 반환합니다.
    """
    if r1.x1 < r2.x0:
        p1_x = r1.x1
        p2_x = r2.x0
    elif r2.x1 < r1.x0:
        p1_x = r1.x0
        p2_x = r2.x1
    else:
        overlap_x0 = max(r1.x0, r2.x0)
        overlap_x1 = min(r1.x1, r2.x1)
        p1_x = p2_x = (overlap_x0 + overlap_x1) / 2

    if r1.y1 < r2.y0:
        p1_y = r1.y1
        p2_y = r2.y0
    elif r2.y1 < r1.y0:
        p1_y = r1.y0
        p2_y = r2.y1
    else:
        overlap_y0 = max(r1.y0, r2.y0)
        overlap_y1 = min(r1.y1, r2.y1)
        p1_y = p2_y = (overlap_y0 + overlap_y1) / 2

    return (p1_x, p1_y), (p2_x, p2_y)

def is_in_matched(cluster, matched_list):
    for _, m in matched_list:
        if (abs(cluster.x0 - m.x0) < 1e-3 and abs(cluster.y0 - m.y0) < 1e-3 and
            abs(cluster.x1 - m.x1) < 1e-3 and abs(cluster.y1 - m.y1) < 1e-3):
            return True
    return False

# ── SQL 저장 함수 ──
def save_to_sql(file_name, table_caption_regions, figure_caption_regions, drawn_table_regions, page_caption_matching):
    # MySQL 연결 정보 수정 (호스트, 사용자, 패스워드, 데이터베이스 이름)
    conn = mysql.connector.connect(
        host='localhost',
        user='root',
        password='00000000',
        database='pdf_parser',
        port=3306
    )

    cursor = conn.cursor()
    
    # 1. pdf_documents 테이블에 파일 정보 저장
    cursor.execute("INSERT INTO pdf_documents (file_name) VALUES (%s)", (file_name,))
    pdf_id = cursor.lastrowid
    
    # 캡션 정보를 저장하기 위한 매핑 (캡션 라벨 -> caption_id)
    caption_mapping = {}
    
    # 2. 캡션 정보를 저장 (table_caption_regions, figure_caption_regions 모두)
    # 각 튜플은 (cap_rect, cap_label, cap_text, page_number, pdf_file_name) 형식이어야 함
    for region in table_caption_regions + figure_caption_regions:
        if len(region) == 5:
            cap_rect, cap_label, cap_text, page_number, pdf_file_name = region
        else:
            cap_rect, cap_label, cap_text, page_number = region
            pdf_file_name = ""
        x0, y0, x1, y1 = cap_rect.x0, cap_rect.y0, cap_rect.x1, cap_rect.y1
        cursor.execute(
            "INSERT INTO captions (caption_name, pdf_id, page_number, caption_text, x0, y0, x1, y1) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (cap_label, pdf_id, page_number, cap_text, x0, y0, x1, y1)
        )
        caption_id = cursor.lastrowid
        caption_mapping[cap_label] = caption_id

    # 매핑: table 캡션 라벨 -> pdf 파일 경로 (table_caption_regions에 pdf_file_name 추가됨)
    table_pdf_mapping = {cap_label: pdf_file_name for (_, cap_label, _, _, pdf_file_name) in table_caption_regions}
    
    # 3. 그려진 표 영역 정보를 저장 (drawn_table_regions)
    for page_number, table_rect, cap_label in drawn_table_regions:
        caption_id = caption_mapping.get(cap_label)
        if caption_id is None:
            continue
        x0, y0, x1, y1 = table_rect.x0, table_rect.y0, table_rect.x1, table_rect.y1
        pdf_file_name = table_pdf_mapping.get(cap_label, '')
        cursor.execute(
            "INSERT INTO tables (caption_id, pdf_file_name, page_number, x0, y0, x1, y1) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (caption_id, pdf_file_name, page_number, x0, y0, x1, y1)
        )
    
    # 4. 클러스터 영역 정보를 저장 (page_caption_matching)
    for page_number, matching in page_caption_matching.items():
        for cap_label, match_data in matching.items():
            # match_data: (cluster_rect, p_cluster, p_cap, distance, pdf_file_name)
            cluster_rect, p_cluster, p_cap, distance, pdf_file_name = match_data
            caption_id = caption_mapping.get(cap_label)
            if caption_id is None:
                continue
            x0, y0, x1, y1 = cluster_rect.x0, cluster_rect.y0, cluster_rect.x1, cluster_rect.y1
            cursor.execute(
                "INSERT INTO clusters (caption_id, page_number, pdf_file_name, x0, y0, x1, y1) VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (caption_id, page_number, pdf_file_name, x0, y0, x1, y1)
            )
    
    conn.commit()
    cursor.close()
    conn.close()

# ── 캡션(테이블 영역) PDF 저장 함수 ──
def save_regions_as_pdf(doc, regions, document_name, drawn_table_regions):
    """
    regions: 리스트 형태로 (cap_rect, cap_label, cap_text, page_number)
    document_name: 원본 PDF의 파일명(확장자 제외)
    drawn_table_regions: 테이블 영역 정보 [(page_number, table_rect, cap_label), ...]
    저장 후 각 튜플에 pdf_file_name을 추가하여 리턴
    """
    base_folder = os.path.join("output", document_name)
    os.makedirs(base_folder, exist_ok=True)
    updated_regions = []
    for region in regions:
        cap_rect, cap_label, cap_text, page_number = region
        # drawn_table_regions에서 동일한 페이지와 캡션 라벨에 해당하는 테이블 영역을 찾음
        table_region = None
        for entry in drawn_table_regions:
            pn, table_rect, table_cap_label = entry
            if pn == page_number and table_cap_label == cap_label:
                table_region = table_rect
                break
        # 테이블 영역이 있으면 해당 영역으로 클립, 없으면 원래 캡션 영역 사용
        clip_rect = table_region if table_region is not None else cap_rect
        timestamp = time.time_ns()
        filename = f"{cap_label}_{timestamp}.pdf"
        filepath = os.path.join(base_folder, filename)
        new_doc = fitz.open()  # 빈 PDF 문서 생성
        new_doc.insert_pdf(doc, from_page=page_number, to_page=page_number)
        new_page = new_doc[0]
        new_page.set_cropbox(clip_rect)
        new_doc.save(filepath)
        new_doc.close()
        updated_regions.append((cap_rect, cap_label, cap_text, page_number, filepath))
    return updated_regions

# ── 클러스터 영역 PDF 저장 함수 (테이블/클러스터 모두 처리) ──
def save_cluster_regions_as_pdf(doc, page_caption_matching, document_name):
    """
    page_caption_matching: {page_number: {cap_label: (cluster_rect, p_cluster, p_cap, distance)}}
    document_name: 원본 PDF의 파일명(확장자 제외)
    저장 후 각 매칭 튜플에 pdf_file_name을 추가하여 리턴
    """
    base_folder = os.path.join("output", document_name)
    os.makedirs(base_folder, exist_ok=True)
    updated_page_caption_matching = {}
    for page_number, captions in page_caption_matching.items():
        updated_captions = {}
        for cap_label, match_data in captions.items():
            cluster_rect, p_cluster, p_cap, distance = match_data
            timestamp = time.time_ns()
            filename = f"{cap_label}_{timestamp}.pdf"
            filepath = os.path.join(base_folder, filename)
            new_doc = fitz.open()
            new_doc.insert_pdf(doc, from_page=page_number, to_page=page_number)
            new_page = new_doc[0]
            new_page.set_cropbox(cluster_rect)
            new_doc.save(filepath)
            new_doc.close()
            updated_captions[cap_label] = (cluster_rect, p_cluster, p_cap, distance, filepath)
        updated_page_caption_matching[page_number] = updated_captions
    return updated_page_caption_matching

def process_pdf(input_path, output_path):
    doc = fitz.open(input_path)
    global_main_blocks = []  # (페이지 번호, 사각형, 텍스트)
    table_caption_regions = []  # (캡션 사각형, 라벨, 캡션 텍스트, 페이지 번호)
    figure_caption_regions = []  # (캡션 사각형, 라벨, 캡션 텍스트, 페이지 번호)
    drawn_table_regions = []  # (페이지 번호, 테이블 영역 사각형, 캡션 라벨)
    drawn_rectangles = []     # (페이지 번호, 사각형)
    
    # 나중에 매칭 정보 저장용 (page_caption_matching)
    page_caption_matching = {}
    entire_col_rect = fitz.Rect()  # 모든 열을 합친 영역

    # ── pending drawing instructions ──
    pending_rect_draws = []          # (page_number, rect, color, width)
    pending_main_text_rect_draws = []  # (page_number, rect, color, width)
    pending_text_inserts = []        # (page_number, text, (x, y), color, fontsize)
    pending_line_draws = []          # (page_number, start_point, end_point, color, width)

    # 캡션 판별 패턴
    fig_pattern = re.compile(r'(?i)^(fig(?:ure)?\.?|첨부자료|첨부파일)(\d+(?:\.\d+)?)(?P<special>.)')
    table_pattern = re.compile(r'(?i)^(table|테이블)(\d+(?:\.\d+)?)(?P<special>.)')

    # ── 텍스트 블럭 처리 ──
    for page in doc:
        text_blocks = page.get_text("blocks")
        for block in text_blocks:
            text = block[4].strip()
            if not text:
                continue
            text_no_space = re.sub(r'\s+', '', text)
            match_fig = fig_pattern.match(text_no_space)
            match_table = table_pattern.match(text_no_space)
            if match_fig:
                special_char = match_fig.group("special")
                if special_char.isalnum() or special_char.isspace():
                    continue
                cap_rect = fitz.Rect(block[:4])
                if cap_rect.get_area() <= 0:
                    continue
                fig_label = f"Figure {match_fig.group(2)}"
                pending_rect_draws.append((page.number, cap_rect, (1, 0, 0), 2))
                pending_text_inserts.append((page.number, fig_label, (cap_rect.x0, cap_rect.y0), (0, 0, 0), 12))
                drawn_rectangles.append((page.number, cap_rect))
                figure_caption_regions.append((cap_rect, fig_label, text, page.number))
            elif match_table:
                special_char = match_table.group("special")
                if special_char.isalnum() or special_char.isspace():
                    continue
                cap_rect = fitz.Rect(block[:4])
                if cap_rect.get_area() <= 0:
                    continue
                table_label = f"Table {match_table.group(2)}"
                pending_rect_draws.append((page.number, cap_rect, (1, 0, 0), 2))
                pending_text_inserts.append((page.number, table_label, (cap_rect.x0, cap_rect.y0), (0, 0, 0), 12))
                table_caption_regions.append((cap_rect, table_label, text, page.number))
                drawn_rectangles.append((page.number, cap_rect))
            else:
                block_rect = fitz.Rect(block[:4])
                global_main_blocks.append((page.number, block_rect, text))
    
    # ── 열(컬럼) 검출 (본문 텍스트 블럭 기반) ──
    for page in doc:
        page_main_blocks = [entry for entry in global_main_blocks if entry[0] == page.number]
        page_columns = []
        remaining_blocks = page_main_blocks.copy()
        while remaining_blocks:
            groups = []
            for entry in remaining_blocks:
                _, rect, _ = entry
                placed = False
                for group in groups:
                    _, rep_rect, _ = group[0]
                    if abs(rect.x0 - rep_rect.x0) <= GROUP_TOLERANCE and abs(rect.x1 - rep_rect.x1) <= GROUP_TOLERANCE:
                        group.append(entry)
                        placed = True
                        break
                if not placed:
                    groups.append([entry])
            dominant = max(groups, key=lambda g: sum(entry[1].get_area() for entry in g))
            col_x_min = min(entry[1].x0 for entry in dominant)
            col_x_max = max(entry[1].x1 for entry in dominant)
            col_y_min = min(entry[1].y0 for entry in dominant)
            col_y_max = max(entry[1].y1 for entry in dominant)
            page_columns.append((col_x_min, col_x_max, col_y_min, col_y_max))
            remaining_blocks = [entry for entry in remaining_blocks if not (entry[1].x1 > col_x_min and entry[1].x0 < col_x_max)]
    
        # 페이지 내 가로선 후보 추출 (높이 < 2, 너비 > 20)
        horz_lines = []
        for obj in page.get_drawings():
            if "rect" not in obj:
                continue
            r = obj["rect"]
            if (r.y1 - r.y0) < 2 and (r.x1 - r.x0) > 20:
                horz_lines.append(r)
    
        tol_x = 10  # 캡션 중앙 기준 x 허용 오차
    
        # ── 테이블 캡션 블럭에 대한 가로선 처리 ──
        for cap_rect, cap_label, text, cap_page in table_caption_regions:
            if cap_page != page.number:
                continue
            cap_center_x = (cap_rect.x0 + cap_rect.x1) / 2
            cap_center_y = (cap_rect.y0 + cap_rect.y1) / 2
    
            selected_lines = []
            for line in horz_lines:
                line_center_x = (line.x0 + line.x1) / 2
                if abs(line_center_x - cap_center_x) <= tol_x:
                    selected_lines.append(line)
            is_iside = False
            if not selected_lines:
                col_range = None
                for col in page_columns:
                    col_x_min, col_x_max, _, _ = col
                    if cap_center_x >= col_x_min and cap_center_x <= col_x_max:
                        col_range = (col_x_min, col_x_max)
                        break
                if col_range is None:
                    col_range = (cap_rect.x0, cap_rect.x1)
                for line in horz_lines:
                    is_iside = True
                    if line.x0 <= col_range[1] + tol_x and line.x1 >= col_range[0] - tol_x:
                        if line not in selected_lines:
                            selected_lines.append(line)
            if not selected_lines:
                table_rect = fitz.Rect(col_range[0], cap_rect.y1, col_range[1], cap_rect.y1 + 20)
                if any(pn == page.number and rect_overlap_ratio(r, table_rect) > 0.8 for (pn, r, _) in drawn_table_regions):
                    pending_rect_draws.append((page.number, table_rect, (0, 0, 1), 2))
                    pending_text_inserts.append((page.number, cap_label, (table_rect.x0, table_rect.y0 - 10), (0, 0, 1), 12))
                else:
                    pending_rect_draws.append((page.number, table_rect, (0, 1, 0), 2))
                    pending_text_inserts.append((page.number, cap_label, (table_rect.x0, table_rect.y0 - 10), (0, 1, 0), 12))
                    drawn_table_regions.append((page.number, table_rect, cap_label))
                continue
    
            best_group = selected_lines
            closest_line = min(best_group, key=lambda r: abs(((r.y0 + r.y1) / 2) - cap_center_y))
            closest_line_center_y = (closest_line.y0 + closest_line.y1) / 2
            direction = 1 if closest_line_center_y - cap_center_y > 0 else -1
            candidate_lines = []
            for line in selected_lines:
                line_center_y = (line.y0 + line.y1) / 2
                if ((line_center_y - cap_center_y) * (closest_line_center_y - cap_center_y) > 0 and not line.intersects(cap_rect)) or is_iside:
                    candidate_lines.append(line)
            boundary_y = None
            for other_cap_rect, other_cap_label, other_text, other_cap_page in table_caption_regions:
                if other_cap_page != page.number:
                    continue
                other_center_x = (other_cap_rect.x0 + other_cap_rect.x1) / 2
                other_center_y = (other_cap_rect.y0 + other_cap_rect.y1) / 2
                if other_cap_rect == cap_rect or abs(other_center_x - cap_center_x) > tol_x:
                    continue
                if direction == 1 and other_center_y > cap_center_y:
                    if boundary_y is None or other_center_y < boundary_y:
                        boundary_y = other_center_y
                elif direction == -1 and other_center_y < cap_center_y:
                    if boundary_y is None or other_center_y > boundary_y:
                        boundary_y = other_center_y
            filtered_candidates = []
            if not is_iside:
                for line in candidate_lines:
                    line_center_y = (line.y0 + line.y1) / 2
                    if direction == 1:
                        if line_center_y > cap_center_y and (boundary_y is None or line_center_y < boundary_y):
                            filtered_candidates.append(line)
                    else:
                        if line_center_y < cap_center_y and (boundary_y is None or line_center_y > boundary_y):
                            filtered_candidates.append(line)
            else:
                filtered_candidates = candidate_lines
    
            x_tol2 = 10
            x_groups = []
            for line in filtered_candidates:
                placed = False
                for group in x_groups:
                    rep_line = group[0]
                    if abs(line.x0 - rep_line.x0) <= x_tol2 and abs(line.x1 - rep_line.x1) <= x_tol2:
                        group.append(line)
                        placed = True
                        break
                if not placed:
                    x_groups.append([line])
    
            closest_group = None
            for group in x_groups:
                if closest_line in group:
                    closest_group = group
                    break
            if closest_group:
                refined_x_min = min(r.x0 for r in closest_group)
                refined_x_max = max(r.x1 for r in closest_group)
                refined_y_min = min(r.y0 for r in closest_group)
                refined_y_max = max(r.y1 for r in closest_group)
                refined_rect = fitz.Rect(refined_x_min, refined_y_min, refined_x_max, refined_y_max)
                if any(pn == page.number and rect_overlap_ratio(r, refined_rect) > 0.8 for (pn, r, _) in drawn_table_regions):
                    pending_rect_draws.append((page.number, refined_rect, (0, 0, 1), 2))
                    pending_text_inserts.append((page.number, cap_label, (refined_rect.x0, refined_rect.y0 - 10), (0, 0, 1), 12))
                    drawn_rectangles.append((page.number, refined_rect))
                    new_candidates = [line for line in selected_lines if line not in closest_group]
                    if new_candidates:
                        x_groups_new = []
                        for line in new_candidates:
                            placed = False
                            for group in x_groups_new:
                                rep_line = group[0]
                                if abs(line.x0 - rep_line.x0) <= x_tol2 and abs(line.x1 - rep_line.x1) <= x_tol2:
                                    group.append(line)
                                    placed = True
                                    break
                            if not placed:
                                x_groups_new.append([line])
                        new_closest_group = None
                        new_closest_line = None
                        min_diff = float('inf')
                        for group in x_groups_new:
                            for line in group:
                                line_center_y = (line.y0 + line.y1) / 2
                                diff = abs(line_center_y - cap_center_y)
                                if diff < min_diff:
                                    min_diff = diff
                                    new_closest_line = line
                                    new_closest_group = group
                        if new_closest_group:
                            new_refined_rect = fitz.Rect(
                                min(r.x0 for r in new_closest_group),
                                min(r.y0 for r in new_closest_group),
                                max(r.x1 for r in new_closest_group),
                                max(r.y1 for r in new_closest_group)
                            )
                            pending_rect_draws.append((page.number, new_refined_rect, (1, 0, 1), 2))
                            drawn_rectangles.append((page.number, new_refined_rect))
                            prev_entry = next((entry for entry in drawn_table_regions if entry[0] == page.number and rect_overlap_ratio(entry[1], refined_rect) > 0.8), None)
                            upper_label = prev_entry[2] if prev_entry is not None else cap_label
                            pending_text_inserts.append((page.number, upper_label, (new_refined_rect.x0, new_refined_rect.y0 - 10), (1, 0, 1), 12))
                        else:
                            pending_rect_draws.append((page.number, refined_rect, (0, 1, 0), 2))
                            pending_text_inserts.append((page.number, cap_label, (refined_rect.x0, refined_rect.y0 - 10), (0, 1, 0), 12))
                            drawn_table_regions.append((page.number, refined_rect, cap_label))
                else:
                    pending_rect_draws.append((page.number, refined_rect, (0, 1, 0), 2))
                    pending_text_inserts.append((page.number, cap_label, (refined_rect.x0, refined_rect.y0 - 10), (0, 1, 0), 12))
                    drawn_table_regions.append((page.number, refined_rect, cap_label))
    
        # End of table caption horizontal line handling
    
    # ── 테이블 영역과 겹치는 본문 텍스트 블럭 제거 ──
    filtered_global_main_blocks = []
    for entry in global_main_blocks:
        page_num, rect, text = entry
        skip = False
        for (pn, table_rect, _) in drawn_table_regions:
            if pn == page_num and rect.intersects(table_rect):
                skip = True
                break
        if not skip:
            filtered_global_main_blocks.append(entry)
    
    # ── 열(컬럼) 검출 (시각화용) ──
    remaining_blocks = filtered_global_main_blocks.copy()
    columns = []
    while remaining_blocks:
        groups = []
        for entry in remaining_blocks:
            pn, rect, _ = entry
            placed = False
            for group in groups:
                _, rep_rect, _ = group[0]
                if abs(rect.x0 - rep_rect.x0) <= GROUP_TOLERANCE and abs(rect.x1 - rep_rect.x1) <= GROUP_TOLERANCE:
                    group.append(entry)
                    placed = True
                    break
            if not placed:
                groups.append([entry])
        dominant = max(groups, key=lambda g: sum(entry[1].get_area() for entry in g))
        columns.append(dominant)
        dom_x0 = min(rect.x0 for (_, rect, _) in dominant)
        dom_x1 = max(rect.x1 for (_, rect, _) in dominant)
        remaining_blocks = [entry for entry in remaining_blocks if not (entry[1].x1 > dom_x0 and entry[1].x0 < dom_x1)]
    
    group_info = []
    for group in columns:
        group_x_min = min(rect.x0 for (_, rect, _) in group)
        group_x_max = max(rect.x1 for (_, rect, _) in group)
        group_width = group_x_max - group_x_min
        group_info.append((group, group_width))
    
    group_info.sort(key=lambda x: x[1], reverse=True)
    
    filtered_groups = []
    if group_info:
        filtered_groups.append(group_info[0])
        for i in range(1, len(group_info)):
            prev_width = filtered_groups[-1][1]
            current_width = group_info[i][1]
            if current_width >= prev_width * 0.9:
                filtered_groups.append(group_info[i])
    
    columns = [grp for (grp, width) in filtered_groups]
    
    for group in columns:
        group_filtered = [entry for entry in group if entry[0] != 0]
        if not group_filtered:
            continue
        group_color = (random.random(), random.random(), random.random())
        group_y_min = min(rect.y0 for (_, rect, _) in group_filtered)
        group_y_max = max(rect.y1 for (_, rect, _) in group_filtered)
        group_x_min = min(rect.x0 for (_, rect, _) in group_filtered)
        group_x_max = max(rect.x1 for (_, rect, _) in group_filtered)
        col_rect = fitz.Rect(group_x_min, group_y_min, group_x_max, group_y_max)
        entire_col_rect |= col_rect
        for entry in group:
            page_num, rect, _ = entry
            pending_main_text_rect_draws.append((page_num, rect, group_color, 1))
            drawn_rectangles.append((page_num, rect))
    
    # ── 이미지 및 드로잉 요소(비 텍스트 요소) 표시 ──
    merged_clusters_by_page = {}
    for page in doc:
        elements_to_cluster = []
        for img in page.get_images(full=True):
            xref = img[0]
            img_rects = page.get_image_rects(xref)
            for rect in img_rects:
                if already_drawn(page.number, rect, drawn_rectangles):
                    continue
                skip = False
                for (pn, table_rect, _) in drawn_table_regions:
                    if pn == page.number and rect_overlap_ratio(rect, table_rect) > 0.8:
                        skip = True
                        break
                if skip:
                    continue
                elements_to_cluster.append(rect)
        for obj in page.get_drawings():
            rect = obj.get("rect")
            skip = False
            if not entire_col_rect.intersects(rect):
                skip = True
            if not skip:
                for (pn, table_rect, _) in drawn_table_regions:
                    if pn == page.number:
                        if rect_overlap_ratio(rect, table_rect) > 0.8:
                            skip = True
                            break
                        if (rect.y1 - rect.y0) < 3:
                            cp = fitz.Point((rect.x0+rect.x1)/2, (rect.y0+rect.y1)/2)
                            if table_rect.contains(cp):
                                skip = True
                                break
                        if (table_rect.contains(rect) or table_rect.intersects(rect)):
                            skip = True
                            break
            if is_in_blocks(page.number, rect, drawn_rectangles):
                skip = True
            if is_intersects_blocks(page.number, rect, drawn_rectangles):
                skip = True
            if skip:
                continue
            elements_to_cluster.append(rect)
    
        clusters_rect = cluster_elements(elements_to_cluster, threshold=20)
        merged_cluster_rects = []
        for cluster in clusters_rect:
            merged_rect = fitz.Rect()
            for r in cluster:
                merged_rect |= r
            if merged_rect.width < 5 or merged_rect.height < 5:
                continue
            merged_cluster_rects.append(merged_rect)
        merged_cluster_rects = merge_overlapping_rects(merged_cluster_rects)
        merged_clusters_by_page[page.number] = merged_cluster_rects
    
    # ── 클러스터 영역 내 캡션 재탐지 ──
    for entry in filtered_global_main_blocks:
        page_num, text_rect, text = entry
        if page_num not in merged_clusters_by_page:
            continue
        page = doc[page_num]
        for cluster_rect in merged_clusters_by_page[page_num]:
            if text_rect.intersects(cluster_rect):
                candidates = subtract_rect(text_rect, cluster_rect)
                for candidate in candidates:
                    candidate_text = page.get_text("text", clip=candidate).strip()
                    if not candidate_text:
                        continue
                    candidate_text_no_space = re.sub(r'\s+', '', candidate_text)
                    match_fig = fig_pattern.match(candidate_text_no_space)
                    match_table = table_pattern.match(candidate_text_no_space)
                    if match_fig:
                        special_char = match_fig.group("special")
                        if special_char.isalnum() or special_char.isspace():
                            continue
                        fig_label = f"Figure {match_fig.group(2)}"
                        pending_rect_draws.append((page_num, candidate, (1, 0, 0), 2))
                        pending_text_inserts.append((page_num, fig_label, (candidate.x0, candidate.y0), (0, 0, 0), 12))
                        drawn_rectangles.append((page_num, candidate))
                        figure_caption_regions.append((candidate, fig_label, candidate_text, page_num))
                    elif match_table:
                        special_char = match_table.group("special")
                        if special_char.isalnum() or special_char.isspace():
                            continue
                        table_label = f"Table {match_table.group(2)}"
                        pending_rect_draws.append((page_num, candidate, (1, 0, 0), 2))
                        pending_text_inserts.append((page_num, table_label, (candidate.x0, candidate.y0), (0, 0, 0), 12))
                        table_caption_regions.append((candidate, table_label, candidate_text, page_num))
                        drawn_rectangles.append((page_num, candidate))
    
    # ── [텍스트 보강 클러스터링 기능 복원] ──
    for page in doc:
        elements_to_cluster = []
        for obj in page.get_text("blocks"):
            rect = fitz.Rect(obj[:4])
            skip = False
            if page.number == 0:
                skip = True
            if not entire_col_rect.intersects(rect):
                skip = True
            if not skip:
                for (pn, table_rect, _) in drawn_table_regions:
                    if pn == page.number:
                        if rect_overlap_ratio(rect, table_rect) > 0.8:
                            skip = True
                            break
                        if (rect.y1 - rect.y0) < 3:
                            cp = fitz.Point((rect.x0+rect.x1)/2, (rect.y0+rect.y1)/2)
                            if table_rect.contains(cp):
                                skip = True
                                break
                        if (table_rect.contains(rect) or table_rect.intersects(rect)):
                            skip = True
                            break
                if is_in_blocks(page.number, rect, drawn_rectangles):
                    skip = True
                if is_intersects_blocks(page.number, rect, drawn_rectangles):
                    skip = True
            if skip:
                continue
            elements_to_cluster.append(rect)
        new_clusters = cluster_elements(elements_to_cluster, threshold=20)
        new_cluster_rects = []
        for cluster in new_clusters:
            merged_rect = fitz.Rect()
            for r in cluster:
                merged_rect |= r
            if merged_rect.width < 5 or merged_rect.height < 5:
                continue
            new_cluster_rects.append(merged_rect)
        new_cluster_rects = merge_overlapping_rects(new_cluster_rects)
        if page.number in merged_clusters_by_page:
            merged_clusters_by_page[page.number].extend(new_cluster_rects)
            merged_clusters_by_page[page.number] = merge_overlapping_rects(merged_clusters_by_page[page.number])
        else:
            merged_clusters_by_page[page.number] = new_cluster_rects
    
    # ── 캡션과 클러스터 영역 매칭 (1:1) ──
    for page in doc:
        clusters = merged_clusters_by_page.get(page.number, [])
        captions_on_page = [(cap_rect, cap_label) for cap_rect, cap_label, _, cap_page in figure_caption_regions if cap_page == page.number]
        if not captions_on_page or not clusters:
            continue
        candidate_clusters = []
        for i, (cap_rect, cap_label) in enumerate(captions_on_page):
            candidates = []
            for j, cluster_rect in enumerate(clusters):
                p_cluster, p_cap = closest_points_between_rectangles(cluster_rect, cap_rect)
                distance = math.hypot(p_cluster[0] - p_cap[0], p_cluster[1] - p_cap[1])
                candidates.append((j, distance, cluster_rect, p_cluster, p_cap))
            candidates.sort(key=lambda x: x[1])
            candidate_clusters.append(candidates)
        match = {}
        def dfs(caption_idx, visited):
            for cand in candidate_clusters[caption_idx]:
                cluster_idx = cand[0]
                if cluster_idx in visited:
                    continue
                visited.add(cluster_idx)
                if cluster_idx not in match or dfs(match[cluster_idx], visited):
                    match[cluster_idx] = caption_idx
                    return True
            return False
        for cap_idx in range(len(captions_on_page)):
            dfs(cap_idx, set())
        for cluster_idx, cap_idx in match.items():
            chosen_candidate = next((cand for cand in candidate_clusters[cap_idx] if cand[0] == cluster_idx), None)
            if chosen_candidate is not None:
                cap_label = captions_on_page[cap_idx][1]
                if page.number not in page_caption_matching:
                    page_caption_matching[page.number] = {}
                page_caption_matching[page.number][cap_label] = (chosen_candidate[2], chosen_candidate[3], chosen_candidate[4], chosen_candidate[1])
    
    # ── 후처리: 매칭되지 않은 클러스터 영역 병합 (캡션과 충돌 시 병합하지 않음) ──
    for page in doc:
        if page.number not in merged_clusters_by_page:
            continue
        if page.number not in page_caption_matching:
            continue
        matched_dict = page_caption_matching[page.number]
        matched_list = [(label, tup[0]) for label, tup in matched_dict.items()]
        unmatched = [cl for cl in merged_clusters_by_page[page.number] if not is_in_matched(cl, matched_list)]
        merge_candidates = []
        for cl in unmatched:
            best_distance = float('inf')
            best_label = None
            best_matched = None
            for label, m in matched_list:
                p1, p2 = closest_points_between_rectangles(cl, m)
                distance = math.hypot(p1[0]-p2[0], p1[1]-p2[1])
                if distance < best_distance:
                    best_distance = distance
                    best_label = label
                    best_matched = m
            if best_label is not None:
                merge_candidates.append((best_distance, best_label, cl))
        merge_candidates.sort(key=lambda x: x[0])
        for dist, label, cl in merge_candidates:
            current_matched = matched_dict[label][0]
            candidate_union = current_matched | cl
            conflict = False
            for pn, dr in drawn_rectangles:
                if pn != page.number:
                    continue
                if candidate_union.intersects(dr) or candidate_union.contains(dr):
                    conflict = True
                    break
            if conflict:
                continue
            for pn, tr, _ in drawn_table_regions:
                if pn != page.number:
                    continue
                if candidate_union.intersects(tr) or candidate_union.contains(tr):
                    conflict = True
                    break
            if conflict:
                continue
            for cap_rect, cap_label, text, cap_page in (figure_caption_regions + table_caption_regions):
                if cap_page != page.number:
                    continue
                if (candidate_union.intersects(cap_rect) or 
                    candidate_union.contains(cap_rect) or 
                    cap_rect.contains(candidate_union)):
                    conflict = True
                    break
            if conflict:
                continue
            matched_dict[label] = (candidate_union, (0,0), (0,0), 0)
            for i, (lbl, m) in enumerate(matched_list):
                if lbl == label:
                    matched_list[i] = (lbl, candidate_union)
                    break
    
    # ── 캡션 영역(테이블 영역)과 클러스터 영역을 개별 PDF로 저장 ──
    # 원본 파일명(확장자 제외)을 document_name으로 사용
    document_name = os.path.splitext(os.path.basename(input_path))[0]
    table_caption_regions = save_regions_as_pdf(doc, table_caption_regions, document_name, drawn_table_regions)
    page_caption_matching = save_cluster_regions_as_pdf(doc, page_caption_matching, document_name)


    # 매칭 결과 표시
    for page in doc:
        matching = page_caption_matching.get(page.number, {})
        for cap_label, match_data in matching.items():
            # match_data: (cluster_rect, p_cluster, p_cap, distance)
            cluster_rect = match_data[0]
            page.draw_rect(cluster_rect, (1,0,1), width=5)
            page.insert_text((cluster_rect.x0, cluster_rect.y0 - 10), cap_label, color=(1,0,1), fontsize=12)
    
    # ── 최종 pending 리스트 처리 ──
    for (page_num, rect, color, width) in pending_rect_draws:
        doc[page_num].draw_rect(rect, color=color, width=width)
    for (page_num, rect, color, width) in pending_main_text_rect_draws:
        doc[page_num].draw_rect(rect, color=color, width=width)
    for (page_num, text, pos, color, fontsize) in pending_text_inserts:
        doc[page_num].insert_text(pos, text, color=color, fontsize=fontsize)
    for (page_num, p1, p2, color, width) in pending_line_draws:
        doc[page_num].draw_line(p1, p2, color=color, width=width)
    
    doc.save(output_path)
    
    
    doc.close()
    
    # PDF 처리 후 SQL에 최종 연결 정보 저장
    save_to_sql(os.path.basename(input_path), table_caption_regions, figure_caption_regions, drawn_table_regions, page_caption_matching)
    print(f"Processed and saved: {os.path.basename(input_path)}")

def main():
    input_dir = "data"
    output_dir = "clustered"
    os.makedirs(output_dir, exist_ok=True)
    for filename in os.listdir(input_dir):
        if filename.lower().endswith(".pdf"):
            input_path = os.path.join(input_dir, filename)
            output_path = os.path.join(output_dir, filename)
            process_pdf(input_path, output_path)
            print(f"Processed: {filename}")
    print("모든 파일 처리 완료!")

if __name__ == '__main__':
    main()
