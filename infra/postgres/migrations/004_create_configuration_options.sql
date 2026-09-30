CREATE TABLE IF NOT EXISTS configuration_options (
    option_id VARCHAR(100) PRIMARY KEY,
    option_type VARCHAR(16) NOT NULL
        CHECK (option_type IN ('gpu', 'ram', 'storage')),
    name TEXT,
    memory_gb INTEGER,
    capacity_gb INTEGER,
    storage_type TEXT,
    price_vnd BIGINT CHECK (price_vnd IS NULL OR price_vnd >= 0),
    source_urls JSONB NOT NULL DEFAULT '[]'::jsonb
        CHECK (jsonb_typeof(source_urls) = 'array'),
    CONSTRAINT configuration_options_nonblank_id_check
        CHECK (length(btrim(option_id)) BETWEEN 1 AND 100),
    CONSTRAINT configuration_options_shape_check CHECK (
        (
            option_type = 'gpu'
            AND name IS NOT NULL AND length(btrim(name)) > 0
            AND memory_gb IS NOT NULL AND memory_gb > 0
            AND capacity_gb IS NULL AND storage_type IS NULL
        ) OR (
            option_type = 'ram'
            AND name IS NULL AND memory_gb IS NULL
            AND capacity_gb IS NOT NULL AND capacity_gb > 0
            AND storage_type IS NULL
        ) OR (
            option_type = 'storage'
            AND name IS NULL AND memory_gb IS NULL
            AND capacity_gb IS NOT NULL AND capacity_gb > 0
            AND (storage_type IS NULL OR length(btrim(storage_type)) > 0)
        )
    )
);

CREATE INDEX IF NOT EXISTS idx_configuration_options_type_id
    ON configuration_options(option_type, option_id);

CREATE TABLE IF NOT EXISTS configuration_option_products (
    option_id VARCHAR(100) NOT NULL,
    product_id VARCHAR(64) NOT NULL,
    CONSTRAINT configuration_option_products_option_fkey
        FOREIGN KEY (option_id) REFERENCES configuration_options(option_id)
        ON DELETE CASCADE,
    CONSTRAINT configuration_option_products_product_fkey
        FOREIGN KEY (product_id) REFERENCES products(id)
        ON DELETE RESTRICT,
    CONSTRAINT configuration_option_products_unique
        PRIMARY KEY (option_id, product_id)
);

CREATE INDEX IF NOT EXISTS idx_configuration_option_products_product_id
    ON configuration_option_products(product_id, option_id);
