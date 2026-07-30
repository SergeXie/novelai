ALTER TABLE mc_book_node
    ADD COLUMN detail_outline_id BIGINT NULL COMMENT '正文节点关联的细纲节点ID' AFTER parent_id,
    ADD KEY idx_bid_detail_outline (bid, detail_outline_id);
