import json
import time
from pathlib import Path
from researchpilot.web import Workspace, Query, safe_error
from researchpilot.pipeline import load_index
from researchpilot.schema import CorpusData

root=Path('artifacts/new-paper-check')
cases=[
('R1','N01','en','What top-5 error did the ResNet ensemble achieve on the ImageNet test set?','3.57%; ensemble, test set',[1,2,6,7]),
('R2','N01','vi','Ensemble ResNet đạt tỷ lệ lỗi top-5 bao nhiêu trên tập kiểm tra ImageNet?','3.57%; ensemble, test set',[1,2,6,7]),
('R3','N01','en','In Table 3, what are the top-1 and top-5 error rates of ResNet-152 under 10-crop testing on ImageNet validation?','21.43% top-1 and 5.71% top-5; not Table 4 values',[6]),
('R4','N01','vi','Trong Table 3, ResNet-152 có lỗi top-1 và top-5 bao nhiêu với 10-crop testing trên ImageNet validation?','21.43% top-1 and 5.71% top-5',[6]),
('T1','N02','en','How long was the Transformer big model trained, and how many GPUs of what type were used?','3.5 days, 8 NVIDIA P100 GPUs',[7,8]),
('T2','N02','vi','Transformer big được huấn luyện trong bao lâu, dùng bao nhiêu GPU và loại GPU nào?','3.5 days, 8 NVIDIA P100 GPUs',[7,8]),
('T3','N02','en','In the base Transformer, how many attention heads are used and what are d_model and d_k?','8 heads, d_model=512, d_k=64',[3,5,9]),
('T4','N02','vi','Transformer base dùng bao nhiêu attention heads, d_model và d_k bằng bao nhiêu?','8 heads, d_model=512, d_k=64',[3,5,9]),
('U1','N01','en','What exact ImageNet top-1 accuracy does this paper report for GPT-4?','ABSTAIN: not reported',[]),
('U2','N02','vi','Paper này báo cáo chính xác bao nhiêu kWh điện tiêu thụ khi huấn luyện Transformer big?','ABSTAIN: no measured kWh reported',[]),
('M1',None,'en','What BLEU scores does Transformer big achieve on WMT 2014 English-to-German and English-to-French?','28.4 EN-DE and 41.8 EN-FR; cite N02',[1,8]),
('C1',['N01','N02'],'en','Compare how ResNet and the Transformer use residual connections. What does each add, and what normalization is used?','ResNet y=F(x)+x, BN; Transformer LayerNorm(x+Sublayer(x)), both papers cited',[]),
]
# Preserve original evaluation questions.
ws=Workspace(Path.cwd())
ws.corpus=CorpusData.model_validate_json((root/'corpus/corpus.json').read_text())
ws.index=load_index(root/'index',ws.config)
ws.papers={p.paper_id:p for p in ws.corpus.manifest.papers}
output=root/'improved-v2-answers.jsonl'
if output.exists(): raise SystemExit('Refusing to overwrite answers')
with output.open('w') as f:
    for ident,papers,lang,q,expected,pages in cases:
        if ident != 'R1': time.sleep(45)
        rec={'id':ident,'question':q,'language':lang,'expected':expected,'expected_pdf_pages':pages,'paper_filter':papers}
        try:
            result=ws.query(Query(question=q,papers=papers if isinstance(papers,list) else [papers] if papers else [],task='compare' if isinstance(papers,list) else 'ask',language=lang))
            rec['result']=result
            print(ident,json.dumps({k:result['answer'][k] for k in ['answer','abstained','citations','warnings']},ensure_ascii=False),flush=True)
        except Exception as exc:
            rec['error']=safe_error(exc)[1]
            print(ident,type(exc).__name__,rec['error'],flush=True)
        f.write(json.dumps(rec,ensure_ascii=False)+'\n');f.flush()
