from langchain_nvidia_ai_endpoints import ChatNVIDIA

client = ChatNVIDIA(
  model="deepseek-ai/deepseek-v3.2",
  api_key="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", 
  temperature=1,
  top_p=0.95,
  max_tokens=8192,
  extra_body={"chat_template_kwargs": {"thinking":True}},
)

for chunk in client.stream([{"role":"user","content":""}]):
  
    if chunk.additional_kwargs and "reasoning_content" in chunk.additional_kwargs:
      print(chunk.additional_kwargs["reasoning_content"], end="")
  
    print(chunk.content, end="")
