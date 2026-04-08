# 爬虫国家说明（中文）

这份文档用于快速查看各国家爬虫脚本、对应表名，以及脚本的大致含义。

- `name`：Scrapy spider 名称
- `target_table`：PostgreSQL 表名
- `base.py`：该国家的通用基类，通常负责建表、增量时间和公共提取逻辑

## 阿尔巴尼亚（albania）

| 文件 | name | target_table | 说明 |
| --- | --- | --- | --- |
| albania.py | albania | alb_news | 阿尔巴尼亚albania爬虫，负责抓取对应站点、机构或栏目内容。 |
| albania_ata.py | albania_ata | alb_ata | 阿尔巴尼亚ata爬虫，负责抓取对应站点、机构或栏目内容。 |
| albania_bank.py | albania_bank | alb_bank | 阿尔巴尼亚bank爬虫，负责抓取对应站点、机构或栏目内容。 |
| albania_finance.py | albania_finance | alb_financa | 阿尔巴尼亚finance爬虫，负责抓取对应站点、机构或栏目内容。 |
| albania_monitor.py | albania_monitor | alb_monitor | 阿尔巴尼亚monitor爬虫，负责抓取对应站点、机构或栏目内容。 |

## 阿尔及利亚（algeria）

| 文件 | name | target_table | 说明 |
| --- | --- | --- | --- |
| algeria_aps.py | algeria_aps | dza_aps | 阿尔及利亚aps爬虫，负责抓取对应站点、机构或栏目内容。 |
| algeria_bank_of_algeria.py | algeria_bank_of_algeria | dza_bank_of_algeria | 阿尔及利亚bank of algeria爬虫，负责抓取对应站点、机构或栏目内容。 |
| algeria_cosob.py | algeria_cosob | dza_cosob | 阿尔及利亚cosob爬虫，负责抓取对应站点、机构或栏目内容。 |
| algeria_dzair_tube.py | algeria_dzair_tube | dza_dzair_tube | 阿尔及利亚dzair tube爬虫，负责抓取对应站点、机构或栏目内容。 |
| algeria_elkhabar.py | algeria_elkhabar | dza_elkhabar | 阿尔及利亚elkhabar爬虫，负责抓取对应站点、机构或栏目内容。 |
| algeria_horizons.py | algeria_horizons | dza_horizons | 阿尔及利亚horizons爬虫，负责抓取对应站点、机构或栏目内容。 |
| algeria_sonatrach.py | algeria_sonatrach | dza_sonatrach | 阿尔及利亚sonatrach爬虫，负责抓取对应站点、机构或栏目内容。 |

## 阿根廷（argentina）

| 文件 | name | target_table | 说明 |
| --- | --- | --- | --- |
| argentina_ambito.py | argentina_ambito | arg_ambito | 阿根廷ambito爬虫，负责抓取对应站点、机构或栏目内容。 |
| argentina_bcra.py | argentina_bcra | arg_bcra | 阿根廷bcra爬虫，负责抓取对应站点、机构或栏目内容。 |
| argentina_clarin.py | argentina_clarin | arg_clarin | 阿根廷clarin爬虫，负责抓取对应站点、机构或栏目内容。 |
| argentina_cnv.py | argentina_cnv | arg_cnv | 阿根廷cnv爬虫，负责抓取对应站点、机构或栏目内容。 |
| argentina_economia_gov.py | argentina_economia_gov | arg_economia_gov | 阿根廷economia gov爬虫，负责抓取对应站点、机构或栏目内容。 |
| argentina_infobae.py | argentina_infobae | arg_infobae | 阿根廷infobae爬虫，负责抓取对应站点、机构或栏目内容。 |
| argentina_lanacion.py | argentina_lanacion | arg_lanacion | 阿根廷lanacion爬虫，负责抓取对应站点、机构或栏目内容。 |
| argentina_pagina12.py | argentina_pagina12 | arg_pagina12 | 阿根廷pagina12爬虫，负责抓取对应站点、机构或栏目内容。 |
| argentina_perfil.py | argentina_perfil | arg_perfil | 阿根廷perfil爬虫，负责抓取对应站点、机构或栏目内容。 |

## 澳大利亚（australia）

| 文件 | name | target_table | 说明 |
| --- | --- | --- | --- |
| australia_afr.py | australia_afr | aus_afr | 澳大利亚afr爬虫，负责抓取对应站点、机构或栏目内容。 |
| australia_asic.py | australia_asic | aus_asic | 澳大利亚asic爬虫，负责抓取对应站点、机构或栏目内容。 |
| australia_rba.py | australia_rba | aus_rba | 澳大利亚rba爬虫，负责抓取对应站点、机构或栏目内容。 |
| australia_treasury.py | australia_treasury | aus_treasury | 澳大利亚treasury爬虫，负责抓取对应站点、机构或栏目内容。 |
| base.py |  |  | 澳大利亚国家通用基类，负责建表、增量时间和公共抓取方法。 |

## 奥地利（austria）

| 文件 | name | target_table | 说明 |
| --- | --- | --- | --- |
| austria_bmaw.py | austria_bmaw | aut_bmaw | 奥地利bmaw爬虫，负责抓取对应站点、机构或栏目内容。 |
| austria_bmf.py | austria_bmf | aut_bmf | 奥地利bmf爬虫，负责抓取对应站点、机构或栏目内容。 |
| austria_diepresse.py | austria_diepresse | aut_diepresse | 奥地利diepresse爬虫，负责抓取对应站点、机构或栏目内容。 |
| austria_oenb.py | austria_oenb | aut_oenb | 奥地利oenb爬虫，负责抓取对应站点、机构或栏目内容。 |
| austria_trend.py | austria_trend | aut_trend | 奥地利trend爬虫，负责抓取对应站点、机构或栏目内容。 |
| base.py |  |  | 奥地利国家通用基类，负责建表、增量时间和公共抓取方法。 |

## 阿塞拜疆（azerbaijan）

| 文件 | name | target_table | 说明 |
| --- | --- | --- | --- |
| bfb.py | bfb | aze_bfb | 阿塞拜疆bfb爬虫，负责抓取对应站点、机构或栏目内容。 |
| economy.py | economy | aze_economy | 阿塞拜疆economy爬虫，负责抓取对应站点、机构或栏目内容。 |

## 巴林（bahrain）

| 文件 | name | target_table | 说明 |
| --- | --- | --- | --- |
| bahrain_cbb.py | bahrain_cbb | bhr_cbb | 巴林cbb爬虫，负责抓取对应站点、机构或栏目内容。 |
| bahrain_edb.py | bahrain_edb | bhr_edb | 巴林edb爬虫，负责抓取对应站点、机构或栏目内容。 |
| bahrain_gdn.py | bahrain_gdn | bhr_gdn | 巴林gdn爬虫，负责抓取对应站点、机构或栏目内容。 |
| bahrain_tra.py | bahrain_tra | bhr_tra | 巴林tra爬虫，负责抓取对应站点、机构或栏目内容。 |
| base.py |  |  | 巴林国家通用基类，负责建表、增量时间和公共抓取方法。 |

## 比利时（belgium）

| 文件 | name | target_table | 说明 |
| --- | --- | --- | --- |
| base.py |  |  | 比利时国家通用基类，负责建表、增量时间和公共抓取方法。 |
| belgium_belgium_portal.py | belgium_belgium_portal | bel_belgium_portal | 比利时belgium portal爬虫，负责抓取对应站点、机构或栏目内容。 |
| belgium_economie_gov.py | belgium_economie_gov | bel_economie_gov | 比利时economie gov爬虫，负责抓取对应站点、机构或栏目内容。 |
| belgium_finance_gov.py | belgium_finance_gov | bel_finance_gov | 比利时finance gov爬虫，负责抓取对应站点、机构或栏目内容。 |
| belgium_fsma.py | belgium_fsma | bel_fsma | 比利时fsma爬虫，负责抓取对应站点、机构或栏目内容。 |

## 巴西（brazil）

| 文件 | name | target_table | 说明 |
| --- | --- | --- | --- |
| brazil_247.py | brazil_247 | bra_247 | 巴西247爬虫，负责抓取对应站点、机构或栏目内容。 |
| brazil_anp.py | brazil_anp | bra_anp | 巴西anp爬虫，负责抓取对应站点、机构或栏目内容。 |
| brazil_ibge.py | brazil_ibge | bra_ibge | 巴西ibge爬虫，负责抓取对应站点、机构或栏目内容。 |

## 中国（china）

| 文件 | name | target_table | 说明 |
| --- | --- | --- | --- |
| caixin_spider.py | caixin |  | 中国caixin spider爬虫，负责抓取对应站点、机构或栏目内容。 |
| news_spider.py | news_cn |  | 中国news spider爬虫，负责抓取对应站点、机构或栏目内容。 |

## 埃及（egypt）

| 文件 | name | target_table | 说明 |
| --- | --- | --- | --- |
| egypt_arabfinance.py | egypt_arabfinance | egy_arabfinance | 埃及arabfinance爬虫，负责抓取对应站点、机构或栏目内容。 |
| egypt_cbe.py | egypt_cbe | egy_cbe | 埃及cbe爬虫，负责抓取对应站点、机构或栏目内容。 |
| egypt_mubasher.py | egypt_mubasher | egy_mubasher | 埃及mubasher爬虫，负责抓取对应站点、机构或栏目内容。 |
| egypt_youm7.py | egypt_youm7 | egy_youm7 | 埃及youm7爬虫，负责抓取对应站点、机构或栏目内容。 |

## 埃塞俄比亚（ethiopia）

| 文件 | name | target_table | 说明 |
| --- | --- | --- | --- |
| ethiopia_addischamber.py | ethiopia_addischamber | ethi_addischamber | 埃塞俄比亚addischamber爬虫，负责抓取对应站点、机构或栏目内容。 |
| ethiopia_ebc.py | ethiopia_ebc | ethi_ebc | 埃塞俄比亚ebc爬虫，负责抓取对应站点、机构或栏目内容。 |
| ethiopia_nbe.py | ethiopia_nbe | ethi_nbe | 埃塞俄比亚nbe爬虫，负责抓取对应站点、机构或栏目内容。 |
| ethiopia_reporter.py | ethiopia_reporter | ethi_reporter | 埃塞俄比亚reporter爬虫，负责抓取对应站点、机构或栏目内容。 |

## 印度（india）

| 文件 | name | target_table | 说明 |
| --- | --- | --- | --- |
| india_cnbctv18.py | india_cnbctv18 | ind_cnbctv18 | 印度cnbctv18爬虫，负责抓取对应站点、机构或栏目内容。 |
| india_digit.py | india_digit | ind_digit | 印度digit爬虫，负责抓取对应站点、机构或栏目内容。 |
| india_economic_times.py | india_economic_times | ind_economic_times | 印度economic times爬虫，负责抓取对应站点、机构或栏目内容。 |
| india_entrackr.py | india_entrackr | ind_entrackr | 印度entrackr爬虫，负责抓取对应站点、机构或栏目内容。 |
| india_gadgets360.py | india_gadgets360 | ind_gadgets360 | 印度gadgets360爬虫，负责抓取对应站点、机构或栏目内容。 |
| india_moneycontrol.py | india_moneycontrol | ind_moneycontrol | 印度moneycontrol爬虫，负责抓取对应站点、机构或栏目内容。 |
| india_moneycontrol_biz.py | india_moneycontrol_biz | ind_moneycontrol_biz | 印度moneycontrol biz爬虫，负责抓取对应站点、机构或栏目内容。 |

## 印度尼西亚（indonesia）

| 文件 | name | target_table | 说明 |
| --- | --- | --- | --- |
| indonesia_bisnis.py | indonesia_bisnis | idn_bisnis | 印度尼西亚bisnis爬虫，负责抓取对应站点、机构或栏目内容。 |
| indonesia_ina_news.py | indonesia_ina_news | idn_ina_news | 印度尼西亚ina news爬虫，负责抓取对应站点、机构或栏目内容。 |
| indonesia_kompas_money.py | indonesia_kompas_money | idn_kompas_money | 印度尼西亚kompas money爬虫，负责抓取对应站点、机构或栏目内容。 |

## 伊朗（iran）

| 文件 | name | target_table | 说明 |
| --- | --- | --- | --- |
| iran_donya.py | iran_donya |  | 伊朗donya爬虫，负责抓取对应站点、机构或栏目内容。 |
| iran_iranintl.py | iran_iranintl | iran_iranintl | 伊朗iranintl爬虫，负责抓取对应站点、机构或栏目内容。 |
| iran_mehr_en.py | iran_mehr_en |  | 伊朗mehr en爬虫，负责抓取对应站点、机构或栏目内容。 |
| iran_presstv.py | iran_presstv |  | 伊朗presstv爬虫，负责抓取对应站点、机构或栏目内容。 |

## 沙特阿拉伯（saudi_arabia）

| 文件 | name | target_table | 说明 |
| --- | --- | --- | --- |
| entarabi_spider.py | saudi_entarabi | saudi_entarabi_news | 沙特阿拉伯entarabi spider爬虫，负责抓取对应站点、机构或栏目内容。 |
| mc_spider.py | saudi_mc | saudi_mc_news | 沙特阿拉伯mc spider爬虫，负责抓取对应站点、机构或栏目内容。 |
| spa_spider.py | saudi_spa | saudi_spa_news | 沙特阿拉伯spa spider爬虫，负责抓取对应站点、机构或栏目内容。 |

## 南非（south_africa）

| 文件 | name | target_table | 说明 |
| --- | --- | --- | --- |
| africa_businessday.py | africa_businessday | afr_businessday | 南非africa businessday爬虫，负责抓取对应站点、机构或栏目内容。 |
| africa_iol.py | africa_iol | afr_iol | 南非africa iol爬虫，负责抓取对应站点、机构或栏目内容。 |
| africa_techcentral.py | africa_techcentral | afr_techcentral | 南非africa techcentral爬虫，负责抓取对应站点、机构或栏目内容。 |
| africa_thepresidency.py | africa_thepresidency | afr_thepresidency | 南非africa thepresidency爬虫，负责抓取对应站点、机构或栏目内容。 |

## 阿联酋（uae）

| 文件 | name | target_table | 说明 |
| --- | --- | --- | --- |
| uae_fxnewstoday.py | uae_fxnewstoday | uae_fxnewstoday | 阿联酋fxnewstoday爬虫，负责抓取对应站点、机构或栏目内容。 |
| uae_moet.py | uae_moet | uae_moet | 阿联酋moet爬虫，负责抓取对应站点、机构或栏目内容。 |
| uae_mubasher.py | uae_mubasher | uae_mubasher | 阿联酋mubasher爬虫，负责抓取对应站点、机构或栏目内容。 |
| uae_wam.py | uae_wam | uae_wam | 阿联酋wam爬虫，负责抓取对应站点、机构或栏目内容。 |

## 丹麦（denmark）

| 文件 | name | target_table | 说明 |
| --- | --- | --- | --- |
| base.py |  |  | 丹麦国家通用基类，负责建表、增量时间和公共抓取方法。 |
| denmark_dst.py | denmark_dst | dnk_dst | 丹麦dst爬虫，负责抓取对应站点、机构或栏目内容。 |
| denmark_finance_gov.py | denmark_finance_gov | dnk_finance_gov | 丹麦finance gov爬虫，负责抓取对应站点、机构或栏目内容。 |
| denmark_finanstilsynet.py | denmark_finanstilsynet | dnk_finanstilsynet | 丹麦finanstilsynet爬虫，负责抓取对应站点、机构或栏目内容。 |
| denmark_nationalbank.py | denmark_nationalbank | dnk_nationalbank | 丹麦nationalbank爬虫，负责抓取对应站点、机构或栏目内容。 |

## 芬兰（finland）

| 文件 | name | target_table | 说明 |
| --- | --- | --- | --- |
| base.py |  |  | 芬兰国家通用基类，负责建表、增量时间和公共抓取方法。 |
| finland_finanssivalvonta.py | finland_finanssivalvonta | fin_finanssivalvonta | 芬兰finanssivalvonta爬虫，负责抓取对应站点、机构或栏目内容。 |
| finland_stat.py | finland_stat | fin_stat | 芬兰stat爬虫，负责抓取对应站点、机构或栏目内容。 |
| finland_suomenpankki.py | finland_suomenpankki | fin_suomenpankki | 芬兰suomenpankki爬虫，负责抓取对应站点、机构或栏目内容。 |
| finland_vm.py | finland_vm | fin_vm | 芬兰vm爬虫，负责抓取对应站点、机构或栏目内容。 |

## 韩国（korea）

| 文件 | name | target_table | 说明 |
| --- | --- | --- | --- |
| base.py |  |  | 韩国国家通用基类，负责建表、增量时间和公共抓取方法。 |
| korea_fsc.py | korea_fsc | kor_fsc | 韩国金融委员会爬虫，负责抓取对应站点、机构或栏目内容。 |
| korea_krx.py | korea_krx | kor_krx | 韩国交易所爬虫，负责抓取对应站点、机构或栏目内容。 |
| korea_moef.py | korea_moef | kor_moef | 韩国经济财政部爬虫，负责抓取对应站点、机构或栏目内容。 |

## 法国（france）

| 文件 | name | target_table | 说明 |
| --- | --- | --- | --- |
| base.py |  |  | 法国国家通用基类，负责建表、增量时间和公共抓取方法。 |
| france_amf.py | france_amf | fra_amf | 法国amf爬虫，负责抓取对应站点、机构或栏目内容。 |
| france_banque_france.py | france_banque_france | fra_banque_france | 法国banque france爬虫，负责抓取对应站点、机构或栏目内容。 |
| france_finance_gov.py | france_finance_gov | fra_finance_gov | 法国finance gov爬虫，负责抓取对应站点、机构或栏目内容。 |
| france_insee.py | france_insee | fra_insee | 法国insee爬虫，负责抓取对应站点、机构或栏目内容。 |
| france_latribune.py | france_latribune | fra_latribune | 法国latribune爬虫，负责抓取对应站点、机构或栏目内容。 |

## 德国（germany）

| 文件 | name | target_table | 说明 |
| --- | --- | --- | --- |
| base.py |  |  | 德国国家通用基类，负责建表、增量时间和公共抓取方法。 |
| germany_bafin.py | germany_bafin | deu_bafin | 德国bafin爬虫，负责抓取对应站点、机构或栏目内容。 |
| germany_bundesbank.py | germany_bundesbank | deu_bundesbank | 德国bundesbank爬虫，负责抓取对应站点、机构或栏目内容。 |
| germany_bundesregierung.py | germany_bundesregierung | deu_bundesregierung | 德国bundesregierung爬虫，负责抓取对应站点、机构或栏目内容。 |
| germany_destatis.py | germany_destatis | deu_destatis | 德国destatis爬虫，负责抓取对应站点、机构或栏目内容。 |
| germany_finance_gov.py | germany_finance_gov | deu_finance_gov | 德国finance gov爬虫，负责抓取对应站点、机构或栏目内容。 |

## 爱尔兰（ireland）

| 文件 | name | target_table | 说明 |
| --- | --- | --- | --- |
| base.py |  |  | 爱尔兰国家通用基类，负责建表、增量时间和公共抓取方法。 |
| ireland_centralbank.py | ireland_centralbank | irl_centralbank | 爱尔兰centralbank爬虫，负责抓取对应站点、机构或栏目内容。 |
| ireland_finance_gov.py | ireland_finance_gov | irl_finance_gov | 爱尔兰finance gov爬虫，负责抓取对应站点、机构或栏目内容。 |
| ireland_independent.py | ireland_independent | irl_independent | 爱尔兰independent爬虫，负责抓取对应站点、机构或栏目内容。 |
| ireland_irish_examiner.py | ireland_irish_examiner | irl_irish_examiner | 爱尔兰irish examiner爬虫，负责抓取对应站点、机构或栏目内容。 |
| ireland_irish_times.py | ireland_irish_times | irl_irish_times | 爱尔兰irish times爬虫，负责抓取对应站点、机构或栏目内容。 |

## 哈萨克斯坦（kazakhstan）

| 文件 | name | target_table | 说明 |
| --- | --- | --- | --- |
| digitalbusiness_spider.py | digitalbusiness |  | 哈萨克斯坦digitalbusiness spider爬虫，负责抓取对应站点、机构或栏目内容。 |
| inbusiness_spider.py | inbusiness |  | 哈萨克斯坦inbusiness spider爬虫，负责抓取对应站点、机构或栏目内容。 |
| informburo_spider.py | informburo |  | 哈萨克斯坦informburo spider爬虫，负责抓取对应站点、机构或栏目内容。 |
| informkz_spider.py | informkz |  | 哈萨克斯坦informkz spider爬虫，负责抓取对应站点、机构或栏目内容。 |
| kapital_spider.py | kapital |  | 哈萨克斯坦kapital spider爬虫，负责抓取对应站点、机构或栏目内容。 |
| lsm_spider.py | lsm |  | 哈萨克斯坦lsm spider爬虫，负责抓取对应站点、机构或栏目内容。 |
| zakon_spider.py | zakon |  | 哈萨克斯坦zakon spider爬虫，负责抓取对应站点、机构或栏目内容。 |

## 阿曼（oman）

| 文件 | name | target_table | 说明 |
| --- | --- | --- | --- |
| base.py |  |  | 阿曼国家通用基类，负责建表、增量时间和公共抓取方法。 |
| oman_daily.py | oman_daily | omn_oman_daily | 阿曼daily爬虫，负责抓取对应站点、机构或栏目内容。 |
| oman_mtcit.py | oman_mtcit | omn_mtcit | 阿曼mtcit爬虫，负责抓取对应站点、机构或栏目内容。 |
| oman_news.py | oman_news | omn_oman_news | 阿曼news爬虫，负责抓取对应站点、机构或栏目内容。 |
| oman_observer.py | oman_observer | omn_oman_observer | 阿曼observer爬虫，负责抓取对应站点、机构或栏目内容。 |

## 巴基斯坦（pakistan）

| 文件 | name | target_table | 说明 |
| --- | --- | --- | --- |
| base.py |  |  | 巴基斯坦国家通用基类，负责建表、增量时间和公共抓取方法。 |
| pakistan_business_recorder.py | pakistan_business_recorder | pak_business_recorder | 巴基斯坦business recorder爬虫，负责抓取对应站点、机构或栏目内容。 |
| pakistan_dawn.py | pakistan_dawn | pak_dawn | 巴基斯坦dawn爬虫，负责抓取对应站点、机构或栏目内容。 |
| pakistan_economy.py | pakistan_economy | pak_economy | 巴基斯坦economy爬虫，负责抓取对应站点、机构或栏目内容。 |
| pakistan_finance_gov.py | pakistan_finance_gov | pak_finance_gov | 巴基斯坦finance gov爬虫，负责抓取对应站点、机构或栏目内容。 |
| pakistan_sbp.py | pakistan_sbp | pak_sbp | 巴基斯坦sbp爬虫，负责抓取对应站点、机构或栏目内容。 |

## 菲律宾（philippines）

| 文件 | name | target_table | 说明 |
| --- | --- | --- | --- |
| base.py |  |  | 菲律宾国家通用基类，负责建表、增量时间和公共抓取方法。 |
| philippines_bsp.py | philippines_bsp | phl_bsp | 菲律宾bsp爬虫，负责抓取对应站点、机构或栏目内容。 |
| philippines_bworld.py | philippines_bworld | phl_bworld | 菲律宾bworld爬虫，负责抓取对应站点、机构或栏目内容。 |
| philippines_dof.py | philippines_dof | phl_dof | 菲律宾dof爬虫，负责抓取对应站点、机构或栏目内容。 |
| philippines_manila_times.py | philippines_manila_times | phl_manila_times | 菲律宾manila times爬虫，负责抓取对应站点、机构或栏目内容。 |

## 塞尔维亚（serbia）

| 文件 | name | target_table | 说明 |
| --- | --- | --- | --- |
| b92.py | b92 | ser_b92 | 塞尔维亚b92爬虫，负责抓取对应站点、机构或栏目内容。 |
| danas.py | danas | ser_danas | 塞尔维亚danas爬虫，负责抓取对应站点、机构或栏目内容。 |
| politika.py | politika | ser_politika | 塞尔维亚politika爬虫，负责抓取对应站点、机构或栏目内容。 |

## 东帝汶（timor_leste）

| 文件 | name | target_table | 说明 |
| --- | --- | --- | --- |
| base.py |  |  | 东帝汶国家通用基类，负责建表、增量时间和公共抓取方法。 |
| timor_leste_finance_gov.py | timor_leste_finance_gov | tls_finance_gov | 东帝汶finance gov爬虫，负责抓取对应站点、机构或栏目内容。 |
| timor_leste_gov_portal.py | timor_leste_gov_portal | tls_gov_portal | 东帝汶gov portal爬虫，负责抓取对应站点、机构或栏目内容。 |
| timor_leste_inetl.py | timor_leste_inetl | tls_inetl | 东帝汶inetl爬虫，负责抓取对应站点、机构或栏目内容。 |
| timor_leste_tatoli.py | timor_leste_tatoli | tls_tatoli | 东帝汶tatoli爬虫，负责抓取对应站点、机构或栏目内容。 |

## 荷兰（netherlands）

| 文件 | name | target_table | 说明 |
| --- | --- | --- | --- |
| base.py |  |  | 荷兰国家通用基类，负责建表、增量时间和公共抓取方法。 |
| netherlands_dnb.py | netherlands_dnb | nld_dnb | 荷兰央行爬虫，抓取英文新闻与金融稳定相关内容。 |
| netherlands_afm.py | netherlands_afm | nld_afm | 荷兰金融市场管理局爬虫，抓取监管新闻与公告。 |
| netherlands_cbs.py | netherlands_cbs | nld_cbs | 荷兰统计局爬虫，抓取英文统计新闻与数据发布。 |
| netherlands_rvo.py | netherlands_rvo | nld_rvo | 荷兰企业局爬虫，抓取英文产业、投资与政策支持新闻。 |
## 吉尔吉斯斯坦

- `kyrgyzstan_akipress.py`
  - `name`: `kyrgyzstan_akipress`
  - `target_table`: `kgz_akipress`
  - 说明：抓取 AKIpress 英文 economy 和 finance 栏目。

- `kyrgyzstan_tazabek.py`
  - `name`: `kyrgyzstan_tazabek`
  - `target_table`: `kgz_tazabek`
  - 说明：抓取 Tazabek 财经新闻。

- `kyrgyzstan_nbkr.py`
  - `name`: `kyrgyzstan_nbkr`
  - `target_table`: `kgz_nbkr`
  - 说明：抓取吉尔吉斯斯坦国家银行英文新闻与公告。

- `kyrgyzstan_gov.py`
  - `name`: `kyrgyzstan_gov`
  - `target_table`: `kgz_gov`
  - 说明：抓取吉尔吉斯斯坦政府英文新闻和新闻发布。

## 老挝（laos）

| 文件 | name | target_table | 说明 |
| --- | --- | --- | --- |
| base.py |  |  | 老挝国家通用基类，负责建表、增量时间和公共抓取方法。 |
| laos_bol.py | laos_bol | lao_bol | 老挝中央银行爬虫，抓取英文公告和 PDF 材料。 |
| laos_kpl.py | laos_kpl | lao_kpl | 老挝通讯社爬虫，抓取英文经济与政府新闻。 |
| laos_mof.py | laos_mof | lao_mof | 老挝财政部爬虫，抓取财政部新闻和公告。 |
| laos_laotiantimes.py | laos_laotiantimes | lao_laotiantimes | 老挝时报爬虫，抓取英文商业和经济新闻。 |
## 老挝补充

| 文件 | name | target_table | 说明 |
| --- | --- | --- | --- |
| laos_lsb.py | laos_lsb | lao_lsb | 老挝统计局爬虫，抓取统计局文章与统计新闻。|
