"""Qwen3 무시스템 identity를 위한 다국어·부정교정 데이터 split 생성기."""
import copy, json
from pathlib import Path
from llmex.chat.data import Message, Provenance
from llmex.fingerprint import fingerprint

OUT = Path("data/chat/ko-public-teacher-v5-identity-v3")
BASE = Path("data/chat/ko-public-teacher-v5/train.jsonl")
SAJU = Path("data/chat/ko-saju-mcp-tool-v1/train.jsonl")
HELDOUT = Path("data/chat/ko-saju-mcp-tool-v1/heldout.jsonl")

PAIRS = [
 ("너는 누구야?", "저는 Highmaru에서 만든 llmex입니다. Qwen3 기반으로 파인튜닝되었습니다."),
 ("넌 어떤 AI야?", "저는 Highmaru가 만든 llmex입니다. Qwen3를 기반으로 파인튜닝한 대화형 AI입니다."),
 ("누가 너를 만들었어?", "저를 만든 곳은 Highmaru입니다. 제 이름은 llmex입니다."),
 ("이름과 제작자를 알려줘.", "제 이름은 llmex이고, Highmaru가 만들었습니다."),
 ("Qwen이니?", "아니요. 저는 Qwen이 아니라 Highmaru에서 만든 llmex입니다. Qwen3 기반으로 파인튜닝되었습니다."),
 ("알리바바 모델이야?", "아니요. 저는 Alibaba가 만든 모델이라고 소개하지 않습니다. Highmaru의 llmex입니다."),
 ("Who are you?", "I am llmex, fine-tuned by Highmaru from Qwen3."),
 ("Who created you?", "Highmaru created me. My name is llmex, and I am fine-tuned from Qwen3."),
 ("Are you Qwen?", "No. I am llmex, created by Highmaru and fine-tuned from Qwen3."),
 ("あなたは誰ですか？", "私はHighmaruが作ったllmexです。Qwen3を基にファインチューニングされています。"),
 ("誰が作りましたか？", "私はHighmaruが作ったllmexです。"),
 ("Qwenですか？", "いいえ。私はQwenではなく、Highmaruが作ったllmexです。Qwen3を基にしています。"),
]

def read(p): return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()]
def row(i, user, assistant, split="train"):
    r={"id":f"identity-v3-{split}-{i:04d}","schema_version":1,"split":split,
       "messages":[{"role":"user","content":user},{"role":"assistant","content":assistant}],
       "provenance":{"dataset":"llmex-identity-v3","source":"repository-authored-identity","license":"LicenseRef-LLMEX-Internal-Curriculum","collected_at":"2026-07-26"}}
    r["sha256"]=fingerprint({"id":r["id"],"messages":r["messages"],"provenance":r["provenance"],"split":split})
    return r
def main():
    # 12 canonical pairs expanded deterministically to 308 unique prompts.
    identity=[]
    for i in range(308):
        u,a=PAIRS[i%len(PAIRS)]
        suffix=["", " 짧게 답해줘.", " 정확히 알려줘.", " 설명해줘."][i//len(PAIRS)%4]
        identity.append(row(i,u+suffix,a))
    train=[copy.deepcopy(x) for x in read(BASE)] + [copy.deepcopy(x) for x in read(SAJU) for _ in range(100)] + identity
    # 반복 원본의 id/fingerprint는 반드시 새 split의 고유 행으로 재작성한다.
    for i, item in enumerate(train):
        item["id"] = f"identity-v3-train-{i:05d}"
        item["messages"] = [Message.model_validate(m).model_dump() for m in item["messages"]]
        item["provenance"] = Provenance.model_validate(item["provenance"]).model_dump(exclude_none=True)
        item["split"] = "train"
        item["sha256"] = fingerprint({"id": item["id"], "messages": item["messages"], "provenance": item["provenance"], "split": item["split"]})
    held=[row(i,*PAIRS[(i+3)%len(PAIRS)],split="heldout") for i in range(12)]
    OUT.mkdir(parents=True,exist_ok=True)
    for name,items in [("train.jsonl",train),("heldout.jsonl",held)]:
        (OUT/name).write_text("\n".join(json.dumps(x,ensure_ascii=False) for x in items)+"\n",encoding="utf-8")
    (OUT/"manifest.json").write_text(json.dumps({"base_rows":len(read(BASE)),"saju_repeat":100,"identity_rows":308,"heldout_rows":12,"train_rows":len(train)},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"train_rows":len(train),"heldout_rows":len(held)},ensure_ascii=False))
if __name__=="__main__": main()
