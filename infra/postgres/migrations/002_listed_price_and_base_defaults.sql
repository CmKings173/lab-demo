-- Safe upgrade for catalogs created with 001 before listed configuration prices existed.
ALTER TABLE products
    ADD COLUMN IF NOT EXISTS listed_price_vnd BIGINT
    CHECK (listed_price_vnd IS NULL OR listed_price_vnd >= 0);

ALTER TABLE products
    ALTER COLUMN base_price_includes SET DEFAULT '["chassis"]'::jsonb;

CREATE INDEX IF NOT EXISTS idx_products_listed_price ON products(listed_price_vnd);
CREATE INDEX IF NOT EXISTS idx_products_max_gpu_slots ON products(max_gpu_slots);
