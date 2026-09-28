import pdfplumber
import re
import json
import datetime

def parse_date_to_iso(date_str):
    formats = [
        "%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y", "%d.%m.%Y",
        "%d %b %Y", "%d %B %Y", "%b %d %Y", "%B %d %Y", "%Y/%m/%d"
    ]
    date_str = date_str.strip()
    date_str = re.sub(r'[.,;]+$', '', date_str)
    for fmt in formats:
        try:
            return datetime.datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            pass
    return date_str

def parse_pdf(file_stream):
    parsed_data = {
        "product_name": "Extracted Product",
        "spec_number": "",
        "effective_date": "",
        "revision_due_date": "",
        "botanical_name": "",
        "plant_part_used": "",
        "standardization": "",
        "production_method": "",
        "shelf_life": "",
        "country_of_origin": "",
        "test_categories": [],
        "additional_info": [],
        "footer_notes": []
    }

    try:
        with pdfplumber.open(file_stream) as pdf:
            full_text = ""
            all_tables = []
            
            for page in pdf.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"
                
                # Extract tables
                tables = page.extract_tables()
                for table in tables:
                    all_tables.append(table)
                    
            # 1. Heuristic text extraction
            spec_match = re.search(r'(?i)spec(?:ification)?(?:.*?)[ :\t]+([A-Z0-9/.-]+)', full_text)
            if spec_match:
                parsed_data["spec_number"] = spec_match.group(1).strip()
                
            prod_match = re.search(r'(?i)product\s*name[\s:]+(.*?)(?:(?=spec(?:ification)?)|(?=\n)|$)', full_text)
            if prod_match:
                parsed_data["product_name"] = prod_match.group(1).strip()
                
            date_match = re.search(r'(?i)effective\s*date[\s:]+([\d]{1,4}[-/.\s]+[a-zA-Z\d]+[-/.\s]+[\d]{1,4})', full_text)
            if date_match:
                parsed_data["effective_date"] = parse_date_to_iso(date_match.group(1))

            rev_match = re.search(r'(?i)revision\s*due\s*date[\s:]+([\d]{1,4}[-/.\s]+[a-zA-Z\d]+[-/.\s]+[\d]{1,4})', full_text)
            if rev_match:
                parsed_data["revision_due_date"] = parse_date_to_iso(rev_match.group(1))

            botanical_match = re.search(r'(?i)botanical(?:.*?)name[\s:]+(.*?)(?:(?=plant\s*part)|(?=\n)|$)', full_text)
            if botanical_match:
                parsed_data["botanical_name"] = botanical_match.group(1).strip()
                
            part_match = re.search(r'(?i)plant\s*part\s*(?:used)?[\s:]+(.*?)(?:(?=\n)|$)', full_text)
            if part_match:
                part_val = part_match.group(1).strip()
                if part_val.lower().startswith("used "):
                    part_val = part_val[5:].strip()
                parsed_data["plant_part_used"] = part_val
                
            std_match = re.search(r'(?i)standardization[\s:]+(.*?)(?:(?=production\s*method)|(?=\n)|$)', full_text)
            if std_match:
                parsed_data["standardization"] = std_match.group(1).strip()
                
            prod_meth_match = re.search(r'(?i)production\s*method[\s:]+(.*?)(?:(?=\n)|$)', full_text)
            if prod_meth_match:
                parsed_data["production_method"] = prod_meth_match.group(1).strip()
                
            shelf_match = re.search(r'(?i)shelf\s*life[\s:]+(.*?)(?:(?=country\s*of)|(?=\n)|$)', full_text)
            if shelf_match:
                parsed_data["shelf_life"] = shelf_match.group(1).strip()
                
            country_match = re.search(r'(?i)country\s*of\s*origin[\s:]+(.*?)(?:(?=\n)|$)', full_text)
            if country_match:
                parsed_data["country_of_origin"] = country_match.group(1).strip()
                
            # 2. Dynamic Table extraction
            current_category = None
            is_additional_info = False
            
            for table in all_tables:
                sl_idx, proto_idx, param_idx, limit_idx = 0, 1, 2, 3
                has_header = False
                
                for row in table:
                    cleaned_row = [str(cell).strip().replace('\n', ' ') if cell else '' for cell in row]
                    row_text = ' '.join(cleaned_row).lower()
                    
                    # Skip rows that are actually the general info header
                    skip_keywords = ['product name', 'botanical name', 'plant part used', 'country of origin', 'production method', 'standardization', 'shelf life']
                    if any(kw in row_text for kw in skip_keywords):
                        continue
                        
                    # Header detection
                    if 'parameter' in row_text and 'limit' in row_text:
                        has_header = True
                        for i, col in enumerate(cleaned_row):
                            col_low = col.lower()
                            if 'sl' in col_low or 'no' in col_low: sl_idx = i
                            elif 'protocol' in col_low or 'method' in col_low: proto_idx = i
                            elif 'limit' in col_low or 'spec' in col_low: limit_idx = i
                            elif 'parameter' in col_low or 'test' in col_low or 'description' in col_low: param_idx = i
                        continue
                        
                    non_empty = [c for c in cleaned_row if c]
                    
                    # Detect Test Categories (e.g., Physical, Chemical)
                    if len(non_empty) == 1:
                        cat_name = non_empty[0].strip()
                        # Ignore if it's too long or contains a colon (likely not a category name)
                        if len(cat_name) > 30 or ':' in cat_name: 
                            continue 
                            
                        if cat_name.upper() == "ADDITIONAL INFORMATION":
                            is_additional_info = True
                            current_category = None
                            continue
                        else:
                            is_additional_info = False
                            current_category = {'category': cat_name, 'rows': []}
                            parsed_data["test_categories"].append(current_category)
                            continue
                        
                    # Process Test Rows
                    if len(non_empty) >= 2:
                        if is_additional_info:
                            parsed_data["additional_info"].append({
                                "parameter": non_empty[0],
                                "detail": " ".join(non_empty[1:])
                            })
                            continue
                            
                        if not current_category:
                            current_category = {'category': 'General Tests', 'rows': []}
                            parsed_data["test_categories"].append(current_category)
                            
                        row_len = len(cleaned_row)
                        
                        # Use dynamic indices if we found a header or have 4 columns
                        if has_header or row_len >= 4:
                            sl_no = cleaned_row[sl_idx] if sl_idx < row_len else ''
                            protocol = cleaned_row[proto_idx] if proto_idx < row_len else ''
                            parameter = cleaned_row[param_idx] if param_idx < row_len else ''
                            limit = cleaned_row[limit_idx] if limit_idx < row_len else ''
                        else:
                            # Fallback heuristics for 2 or 3 columns
                            if row_len == 3:
                                sl_no = ''
                                protocol = cleaned_row[0]
                                parameter = cleaned_row[1]
                                limit = cleaned_row[2]
                            elif row_len == 2:
                                sl_no, protocol = '', ''
                                parameter = cleaned_row[0]
                                limit = cleaned_row[1]
                                
                        # Clean up formatting artifact from PDF
                        if sl_no.startswith("1010 "):
                            sl_no = sl_no.replace("1010 ", "")
                                
                        current_category['rows'].append({
                            'sl_no': sl_no, 'protocol': protocol, 'parameter': parameter, 'limit': limit
                        })
                        
            # Clean up empty categories
            parsed_data["test_categories"] = [c for c in parsed_data["test_categories"] if len(c['rows']) > 0]

    except Exception as e:
        print("Error parsing PDF:", e)
        
    return parsed_data
