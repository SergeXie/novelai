ALTER TABLE mc_ai_models
    ADD COLUMN max_word_count INT NOT NULL DEFAULT 0
    COMMENT '模型单次请求提示词字数上限，0表示不限制'
    AFTER max_tokens;
