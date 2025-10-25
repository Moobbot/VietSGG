# VietSGG: A Benchmark Dataset and Baseline for Vietnamese Scene Graph Generation

**VietSGG** is the **first benchmark dataset for Vietnamese Scene Graph Generation (SGG)**.  
It extends the **UIT-ViIC** image corpus with dense object and relationship annotations aligned to a **standardized Vietnamese ontology**.

📄 **Accepted at EAI GOODTECHS 2025**  
> Ngo Duc Tam, Tran Thi Ngan, Tran Manh Tuan, Pham Minh Duc, Nguyen Duc Quang Anh.  
> *VietSGG: A Benchmark Dataset and Baseline Models for Vietnamese Scene Graph Generation.*  
> In Proceedings of the **EAI International Conference on Smart Objects and Technologies for Social Good (GOODTECHS 2025)**.  
> [https://goodtechs.eai-conferences.org/2025/](https://goodtechs.eai-conferences.org/2025/)


---

## **1. Prerequisites**

- Python 3.10
- Internet connection (for dataset download)
- The following files are included or required:

  - `download_uitvic.py`
  - `rename_image.py`
  - `requirements.txt`
  - `VietSGG` source directory

---

## **2. Environment Setup**

### **Windows**

```bash
py -3.10 -m venv .venv
.venv\Scripts\activate
```

### **Linux / macOS**

```bash
python3.10 -m venv .venv
source .venv/bin/activate
```

Upgrade and install dependencies:

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## **3. Dataset Preparation**

### **Step 1. Download UIT-ViIC Base Images**

Run:

```bash
python download_uitvic.py
```

This script automatically downloads the UIT-ViIC dataset (≈3,850 images) used as the visual base of VietSGG.
Ensure you run it **from the same directory** as the script or adjust the path inside it.

### **Step 2. Normalize Image Names**

Run:

```bash
python rename_image.py
```

This step **renames and standardizes filenames** to comply with VietSGG conventions.
If you use a custom folder structure, update the input/output paths in the script.

---

## **4. Running VietSGG**
After preparing the dataset, you can now run VietSGG pipelines VietSGG.ipynb

---

## **5. Troubleshooting**

| Issue                   | Possible Fix                                                              |
| ----------------------- | ------------------------------------------------------------------------- |
| Python version mismatch | Install Python 3.10 or use `pyenv` / `conda`                              |
| Permission denied       | Run with proper file access or modify directory permissions               |
| Dataset not found       | Verify output path in `download_uitvic.py` and input in `rename_image.py` |

---

## **6. Citation**

If you use **VietSGG** in your research, please cite:

```bibtex
@inproceedings{ngo2025vietsgg,
  title     = {VietSGG: A Benchmark Dataset and Baseline Models for Vietnamese Scene Graph Generation},
  author    = {Ngo, Duc Tam and Tran, Thi Ngan and Tran, Manh Tuan and Pham, Minh Duc and Nguyen, Duc Quang Anh},
  booktitle = {Proceedings of the International Conference on Computer Science and Information Technology (ICSIT)},
  year      = {2025},
  note      = {Vietnam National University, Hanoi}
}
```

---

## **7. Repository Structure**

```
.
├── README.md
├── requirements.txt
├── download_uitvic.py
├── rename_image.py
├── VietSGG.ipynb                 # End-to-end demo / pipelines
├── vietsgg/                      # Dataset root
│   ├── images/                   # Image directory
│   ├── train.json                # Object annotations (COCO-style)
│   ├── val.json                  # Validation annotations
│   └── rel.json                  # Relationship triplets (subject, predicate, object)
```

---

## **8. License and Availability**

- VietSGG will be released for **research and educational use only** under a permissive license.
- Repository: [https://github.com/Moobbot/VietSSG](https://github.com/Moobbot/VietSSG)