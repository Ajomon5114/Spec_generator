import json
import re

def clean_json_string(s):
    # Remove control characters, except newline and tab
    return re.sub(r'[\x00-\x08\x0b-\x1f]', '', s)

def extract():
    with open('specifications.db', 'rb') as f:
        data = f.read()

    idx = data.find(b'{"product_name":')
    while idx != -1:
        # scan forward for matching braces
        brace_count = 0
        in_string = False
        escape = False
        
        for i in range(idx, len(data)):
            c = data[i:i+1]
            if escape:
                escape = False
                continue
                
            if c == b'\\':
                escape = True
            elif c == b'"':
                in_string = not in_string
            elif not in_string:
                if c == b'{':
                    brace_count += 1
                elif c == b'}':
                    brace_count -= 1
                    
                    if brace_count == 0:
                        obj = data[idx:i+1]
                        
                        try:
                            # 1. Decode ignoring errors
                            jstr = obj.decode('utf-8', errors='ignore')
                            # 2. Fix the corrupted string they added if it is there
                            jstr = jstr.replace('col":"Organoleptic", "Internal method"', 'col": "Internal method"')
                            # 3. Clean control characters that VS code might have inserted
                            jstr = clean_json_string(jstr)
                            
                            # There's another error: Expecting ',' delimiter
                            # Let's see if we can just parse it
                            parsed = json.loads(jstr)
                            print('Recovered:', parsed['product_name'])
                            safe_name = parsed['product_name'].replace('/', '_').replace(' ', '_').replace(':', '_')
                            with open(f'template_{safe_name}.json', 'w') as outf:
                                json.dump(parsed, outf, indent=2)
                        except Exception as e:
                            print('Error parsing JSON at idx', idx, ':', e)
                            # Dump the broken json so we can see what's wrong with it
                            with open(f'broken_{idx}.txt', 'w', encoding='utf-8') as b:
                                b.write(jstr)
                        
                        break
                        
        idx = data.find(b'{"product_name":', idx + 1)
        
extract()
