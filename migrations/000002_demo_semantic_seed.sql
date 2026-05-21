INSERT INTO sources (
    spider_name,
    display_name,
    domain,
    country_code,
    country,
    language,
    organization,
    updated_at
)
VALUES
    ('demo_global', 'Demo Global Wire', 'demo.example.com', 'EU', 'European Union', 'en', 'European Commission', CURRENT_TIMESTAMP),
    ('demo_us_tech', 'Demo US Tech', 'demo-us.example.com', 'US', 'United States', 'en', 'OpenAI', CURRENT_TIMESTAMP),
    ('demo_energy_asia', 'Demo Energy Asia', 'demo-asia.example.com', 'ID', 'Indonesia', 'en', 'ASEAN', CURRENT_TIMESTAMP)
ON CONFLICT (spider_name) DO UPDATE SET
    display_name = EXCLUDED.display_name,
    domain = EXCLUDED.domain,
    country_code = EXCLUDED.country_code,
    country = EXCLUDED.country,
    language = EXCLUDED.language,
    organization = EXCLUDED.organization,
    updated_at = CURRENT_TIMESTAMP;

INSERT INTO articles (
    source_id,
    source_url,
    title_original,
    content_raw_html,
    content_cleaned,
    content_markdown,
    content_plain,
    images,
    publish_time,
    author,
    language,
    section,
    country_code,
    country,
    company,
    category,
    content_hash,
    extraction_status,
    translation_status,
    embedding_status,
    updated_at
)
SELECT
    s.id,
    seed.source_url,
    seed.title_original,
    seed.content_plain,
    seed.content_plain,
    seed.content_plain,
    seed.content_plain,
    '[]'::jsonb,
    seed.publish_time,
    seed.author,
    seed.language,
    seed.section,
    seed.country_code,
    seed.country,
    seed.company,
    seed.category,
    seed.content_hash,
    'completed',
    'completed',
    'pending',
    CURRENT_TIMESTAMP
FROM (
    VALUES
        (
            'demo_global',
            'https://demo.example.com/eu-ai-liability',
            'EU approves AI liability framework',
            'The European Union approved a new AI liability framework focused on enterprise accountability, model governance, and cross-border compliance for generative AI vendors.',
            TIMESTAMP '2025-06-09 09:00:00',
            'Demo Editor',
            'en',
            'policy',
            'EU',
            'European Union',
            NULL,
            'Regulation',
            'demo-eu-ai-liability'
        ),
        (
            'demo_global',
            'https://demo.example.com/eu-ai-governance-fines',
            'EU finalizes governance rules and fines for AI providers',
            'European regulators finalized governance obligations and financial penalties for AI providers operating in the single market, with new compliance checkpoints for frontier models.',
            TIMESTAMP '2025-06-10 11:30:00',
            'Demo Editor',
            'en',
            'policy',
            'EU',
            'European Union',
            NULL,
            'Regulation',
            'demo-eu-ai-governance-fines'
        ),
        (
            'demo_us_tech',
            'https://demo-us.example.com/openai-europe-compliance',
            'OpenAI expands Europe compliance team after new EU rules',
            'OpenAI expanded its Europe compliance team and internal governance process after new EU rules raised requirements on disclosure, risk management, and enterprise readiness.',
            TIMESTAMP '2025-06-11 14:20:00',
            'Demo Tech Desk',
            'en',
            'technology',
            'US',
            'United States',
            'OpenAI',
            'Technology',
            'demo-openai-europe-compliance'
        ),
        (
            'demo_energy_asia',
            'https://demo-asia.example.com/asean-energy-transition',
            'ASEAN summit highlights regional energy transition financing',
            'ASEAN leaders highlighted transition financing, grid modernization, and LNG investment coordination during a regional energy summit focused on industrial resilience.',
            TIMESTAMP '2025-06-07 08:40:00',
            'Demo Asia Desk',
            'en',
            'economy',
            'ID',
            'Indonesia',
            NULL,
            'Energy',
            'demo-asean-energy-transition'
        )
) AS seed(
    spider_name,
    source_url,
    title_original,
    content_plain,
    publish_time,
    author,
    language,
    section,
    country_code,
    country,
    company,
    category,
    content_hash
)
JOIN sources s ON s.spider_name = seed.spider_name
ON CONFLICT (source_url) DO UPDATE SET
    source_id = EXCLUDED.source_id,
    title_original = EXCLUDED.title_original,
    content_raw_html = EXCLUDED.content_raw_html,
    content_cleaned = EXCLUDED.content_cleaned,
    content_markdown = EXCLUDED.content_markdown,
    content_plain = EXCLUDED.content_plain,
    images = EXCLUDED.images,
    publish_time = EXCLUDED.publish_time,
    author = EXCLUDED.author,
    language = EXCLUDED.language,
    section = EXCLUDED.section,
    country_code = EXCLUDED.country_code,
    country = EXCLUDED.country,
    company = EXCLUDED.company,
    category = EXCLUDED.category,
    content_hash = EXCLUDED.content_hash,
    extraction_status = 'completed',
    translation_status = 'completed',
    updated_at = CURRENT_TIMESTAMP;

INSERT INTO article_translations (
    article_id,
    target_language,
    title_translated,
    summary_translated,
    content_translated,
    translator,
    status,
    updated_at
)
SELECT
    a.id,
    'zh-CN',
    seed.title_translated,
    seed.summary_translated,
    seed.content_translated,
    'demo-seed',
    'completed',
    CURRENT_TIMESTAMP
FROM (
    VALUES
        (
            'https://demo.example.com/eu-ai-liability',
            'EU AI liability framework approved',
            'The EU approved a new AI liability framework covering enterprise accountability, model governance, and cross-border compliance.',
            'The EU approved a new AI liability framework covering enterprise accountability, model governance, and compliance requirements for generative AI vendors.'
        ),
        (
            'https://demo.example.com/eu-ai-governance-fines',
            'EU finalizes AI governance rules and fines',
            'European regulators finalized AI provider governance obligations and penalty mechanisms for frontier model compliance.',
            'European regulators finalized governance obligations and penalty mechanisms for AI providers, adding compliance checkpoints for frontier models.'
        ),
        (
            'https://demo-us.example.com/openai-europe-compliance',
            'OpenAI expands Europe compliance team',
            'OpenAI expanded its Europe compliance and governance team after new EU rules raised disclosure and risk management requirements.',
            'After new EU rules were introduced, OpenAI expanded its Europe compliance team and internal governance process to meet disclosure, risk management, and enterprise readiness requirements.'
        ),
        (
            'https://demo-asia.example.com/asean-energy-transition',
            'ASEAN summit focuses on energy transition financing',
            'ASEAN leaders emphasized transition financing, grid upgrades, and LNG investment coordination.',
            'ASEAN leaders emphasized energy transition financing, grid modernization, and LNG investment coordination during a regional summit focused on industrial resilience.'
        )
) AS seed(source_url, title_translated, summary_translated, content_translated)
JOIN articles a ON a.source_url = seed.source_url
ON CONFLICT (article_id, target_language) DO UPDATE SET
    title_translated = EXCLUDED.title_translated,
    summary_translated = EXCLUDED.summary_translated,
    content_translated = EXCLUDED.content_translated,
    translator = EXCLUDED.translator,
    status = 'completed',
    updated_at = CURRENT_TIMESTAMP;
