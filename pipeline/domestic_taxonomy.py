DOMESTIC_CATEGORY_ALIASES = {
    "政治": "政治",
    "经济": "经济",
    "金融": "经济",
    "贸易": "经济",
    "产业": "经济",
    "能源": "经济",
    "军事": "军事",
    "法规": "法规",
    "法律": "法规",
    "监管": "法规",
    "科技": "科技",
    "社会": "社会",
    "文化": "社会",
    "教育": "社会",
    "体育": "社会",
    "民生": "社会",
    "环境": "环境",
    "生态": "环境",
    "气候": "环境",
    "污染": "环境",
}

PROVINCE_ALIASES = {
    "北京": ["北京", "北京市"],
    "天津": ["天津", "天津市"],
    "上海": ["上海", "上海市"],
    "重庆": ["重庆", "重庆市"],
    "河北": ["河北", "河北省"],
    "山西": ["山西", "山西省"],
    "辽宁": ["辽宁", "辽宁省"],
    "吉林": ["吉林", "吉林省"],
    "黑龙江": ["黑龙江", "黑龙江省"],
    "江苏": ["江苏", "江苏省"],
    "浙江": ["浙江", "浙江省"],
    "安徽": ["安徽", "安徽省"],
    "福建": ["福建", "福建省"],
    "江西": ["江西", "江西省"],
    "山东": ["山东", "山东省"],
    "河南": ["河南", "河南省"],
    "湖北": ["湖北", "湖北省"],
    "湖南": ["湖南", "湖南省"],
    "广东": ["广东", "广东省"],
    "海南": ["海南", "海南省"],
    "四川": ["四川", "四川省"],
    "贵州": ["贵州", "贵州省"],
    "云南": ["云南", "云南省"],
    "陕西": ["陕西", "陕西省"],
    "甘肃": ["甘肃", "甘肃省"],
    "青海": ["青海", "青海省"],
    "内蒙古": ["内蒙古", "内蒙古自治区"],
    "广西": ["广西", "广西壮族自治区"],
    "西藏": ["西藏", "西藏自治区"],
    "宁夏": ["宁夏", "宁夏回族自治区"],
    "新疆": ["新疆", "新疆维吾尔自治区"],
}

CITY_TO_PROVINCE = {
    "北京": ("北京", ["北京", "北京市"]),
    "天津": ("天津", ["天津", "天津市"]),
    "上海": ("上海", ["上海", "上海市"]),
    "重庆": ("重庆", ["重庆", "重庆市"]),
    "广州": ("广东", ["广州", "广州市"]),
    "深圳": ("广东", ["深圳", "深圳市"]),
    "珠海": ("广东", ["珠海", "珠海市"]),
    "佛山": ("广东", ["佛山", "佛山市"]),
    "东莞": ("广东", ["东莞", "东莞市"]),
    "中山": ("广东", ["中山", "中山市"]),
    "苏州": ("江苏", ["苏州", "苏州市"]),
    "南京": ("江苏", ["南京", "南京市"]),
    "无锡": ("江苏", ["无锡", "无锡市"]),
    "常州": ("江苏", ["常州", "常州市"]),
    "南通": ("江苏", ["南通", "南通市"]),
    "杭州": ("浙江", ["杭州", "杭州市"]),
    "宁波": ("浙江", ["宁波", "宁波市"]),
    "温州": ("浙江", ["温州", "温州市"]),
    "绍兴": ("浙江", ["绍兴", "绍兴市"]),
    "合肥": ("安徽", ["合肥", "合肥市"]),
    "福州": ("福建", ["福州", "福州市"]),
    "厦门": ("福建", ["厦门", "厦门市"]),
    "泉州": ("福建", ["泉州", "泉州市"]),
    "南昌": ("江西", ["南昌", "南昌市"]),
    "济南": ("山东", ["济南", "济南市"]),
    "青岛": ("山东", ["青岛", "青岛市"]),
    "烟台": ("山东", ["烟台", "烟台市"]),
    "郑州": ("河南", ["郑州", "郑州市"]),
    "武汉": ("湖北", ["武汉", "武汉市"]),
    "宜昌": ("湖北", ["宜昌", "宜昌市"]),
    "长沙": ("湖南", ["长沙", "长沙市"]),
    "株洲": ("湖南", ["株洲", "株洲市"]),
    "成都": ("四川", ["成都", "成都市"]),
    "绵阳": ("四川", ["绵阳", "绵阳市"]),
    "贵阳": ("贵州", ["贵阳", "贵阳市"]),
    "昆明": ("云南", ["昆明", "昆明市"]),
    "西安": ("陕西", ["西安", "西安市"]),
    "兰州": ("甘肃", ["兰州", "兰州市"]),
    "西宁": ("青海", ["西宁", "西宁市"]),
    "呼和浩特": ("内蒙古", ["呼和浩特", "呼和浩特市"]),
    "南宁": ("广西", ["南宁", "南宁市"]),
    "拉萨": ("西藏", ["拉萨", "拉萨市"]),
    "银川": ("宁夏", ["银川", "银川市"]),
    "乌鲁木齐": ("新疆", ["乌鲁木齐", "乌鲁木齐市"]),
    "海口": ("海南", ["海口", "海口市"]),
    "石家庄": ("河北", ["石家庄", "石家庄市"]),
    "唐山": ("河北", ["唐山", "唐山市"]),
    "太原": ("山西", ["太原", "太原市"]),
    "沈阳": ("辽宁", ["沈阳", "沈阳市"]),
    "大连": ("辽宁", ["大连", "大连市"]),
    "长春": ("吉林", ["长春", "长春市"]),
    "哈尔滨": ("黑龙江", ["哈尔滨", "哈尔滨市"]),
}


def normalize_domestic_category(category: str | None) -> str | None:
    if not category:
        return None
    normalized = category.strip()
    return DOMESTIC_CATEGORY_ALIASES.get(normalized, normalized)


def infer_domestic_category(
    title: str | None,
    content: str | None,
    section: str | None,
    raw_category: str | None,
) -> str | None:
    normalized = normalize_domestic_category(raw_category)
    if normalized and normalized not in {"headline", "news_headline"}:
        return normalized

    text = " ".join(filter(None, [title, content, section])).lower()
    if not text:
        return normalized

    keyword_groups = [
        ("军事", ["军事", "国防", "部队", "海军", "空军", "火箭军", "演习", "武器", "军队"]),
        ("法规", ["法规", "法律", "条例", "规定", "办法", "规则", "监管", "执法", "处罚", "合规"]),
        ("科技", ["科技", "量子", "ai", "人工智能", "芯片", "半导体", "机器人", "算力", "卫星", "通信"]),
        ("环境", ["环境", "生态", "低碳", "绿色", "污染", "气候", "碳", "减排", "环保", "储能"]),
        ("社会", ["民生", "教育", "医疗", "就业", "文旅", "旅游", "文化", "体育", "消费", "养老"]),
        ("政治", ["国务院", "中央", "外交", "政府", "书记", "主任", "部长", "峰会", "会议", "政策"]),
        ("经济", ["经济", "金融", "财政", "投资", "产业", "企业", "外贸", "出口", "市场", "价格", "汽车"]),
    ]
    for category_name, keywords in keyword_groups:
        if any(keyword in text for keyword in keywords):
            return category_name

    if (section or "").strip().lower() == "finance":
        return "经济"
    return "其他"


def infer_domestic_location(title: str | None, content: str | None) -> tuple[str | None, str | None]:
    text = " ".join(filter(None, [title, content]))
    if not text:
        return None, None

    for city, (province, aliases) in CITY_TO_PROVINCE.items():
        if any(alias in text for alias in aliases):
            return province, city

    for province, aliases in PROVINCE_ALIASES.items():
        if any(alias in text for alias in aliases):
            if province in {"北京", "天津", "上海", "重庆"}:
                return province, province
            return province, None
    return None, None


def split_organization_and_company(value: str | None) -> tuple[str | None, str | None]:
    if not value:
        return None, None

    text = value.strip()
    if not text:
        return None, None

    separators = [",", "，", "、", ";", "；"]
    has_list = any(sep in text for sep in separators)
    company_markers = ("公司", "集团", "资本", "基金", "银行", "证券", "科技", "汽车", "电投", "交易所")
    org_markers = ("协会", "部", "局", "委", "厅", "政府", "法院", "检察院", "办", "中心", "研究院")

    if any(marker in text for marker in org_markers) and not has_list:
        return text, None

    if has_list:
        parts = [part.strip() for sep in separators for part in text.split(sep)]
        parts = [part for part in parts if part]
        if len(parts) >= 2 and any(any(marker in part for marker in company_markers) for part in parts):
            return None, text

    if any(marker in text for marker in company_markers):
        return None, text

    return text, None
