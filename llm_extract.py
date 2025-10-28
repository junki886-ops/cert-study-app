from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers import PydanticOutputParser
from langchain_huggingface import HuggingFacePipeline
from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
from schemas import PageExtraction

# -------------------------
# 모델 로드 (경량 모델: Qwen2.5-1.8B)
# -------------------------
MODEL_ID = "Qwen/Qwen2.5-1.8B-Instruct"

tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
model = AutoModelForCausalLM.from_pretrained(
    MODEL_ID,
    device_map="auto",   # GPU 있으면 "auto", CPU만 있으면 "cpu"
    torch_dtype="auto"
)

pipe = pipeline(
    "text-generation",
    model=model,
    tokenizer=tokenizer,
    max_new_tokens=512,
    temperature=0.0
)

llm = HuggingFacePipeline(pipeline=pipe)

# -------------------------
# 파서 (JSON → Pydantic)
# -------------------------
parser = PydanticOutputParser(pydantic_object=PageExtraction)

# -------------------------
# 프롬프트 템플릿
# -------------------------
SYSTEM = """당신은 시험 문제를 JSON으로 추출하는 도우미입니다.
반드시 {format_instructions} 형식을 지키세요.
"""

HUMAN = """페이지 원문:

요구사항:
- 문제 단위로 분리하여 items 배열에 담아주세요.
- options는 반드시 A,B,C,D 형태의 키만 사용하세요.
- answer는 options 키 중 하나여야 합니다.
- 해설이 없으면 간단히 작성하세요.
"""

prompt = ChatPromptTemplate.from_messages([
    ("system", SYSTEM),
    ("human", HUMAN),
]).partial(format_instructions=parser.get_format_instructions())

# 최종 체인 (입력 → LLM → JSON 파싱)
chain = prompt | llm | parser
