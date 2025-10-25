import json

input_path = 'data/relationships_vi_coco_uitvic_train-final.json'
output_path = 'data/relationships_vi_coco_uitvic_train-final.json'

with open(input_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

filtered_data = [item for item in data if item.get('relationships') != []]

with open(output_path, 'w', encoding='utf-8') as f:
    json.dump(filtered_data, f, ensure_ascii=False, indent=2)