import psycopg2
from datetime import datetime

# Database connection parameters
def get_conn():
    return psycopg2.connect(
        dbname="scrapy_db",
        user="your_user",
        password="your_password",
        host="postgres",
        port="5432"
    )

articles = [
    {
        "url": "https://financa.gov.al/newsroom/ministri-malaj-prezanton-ne-kuvend-marreveshjen-per-financimin-e-programit-infrastruktura-bashkiake-v-faza-ii/",
        "title": "Ministri Malaj prezanton në Kuvend marrëveshjen për financimin e programit “Infrastruktura Bashkiake V – faza II”",
        "publish_time": "2026-03-05",
        "content": "Ministri i Financave, Petrit Malaj, prezantoi në Kuvend projektligjin “Për ratifikimin e marrëveshjes së huas, ndërmjet Republikës së Shqipërisë, përfaqësuar nga Ministria e Financave (huamarrësi), dhe KfW Frankfurt am Main (KfW), për programin “Infrastruktura bashkiake V – faza II””. Përmes kësaj marrëveshjeje mundësohet një financim prej 47 milionë euro për programin e mësipërm."
    },
    {
        "url": "https://financa.gov.al/newsroom/permbledhje-e-performances-paraprake-te-te-ardhurave-dhe-shpenzimeve-per-janar-2026/",
        "title": "Përmbledhje e Performancës Paraprake të të Ardhurave dhe Shpenzimeve për Janar 2026",
        "publish_time": "2026-03-04",
        "content": "Performanca paraprake e treguesve fiskalë të konsoliduar për muajin Janar 2026 reflekton ecurinë e mbledhjes së të ardhurave dhe realizimit të shpenzimeve. Të ardhurat totale, për muajin Janar 2026, arritën në rreth 69.8 miliardë lekë. Shpenzimet e përgjithshme publike, për muajin e parë të vitit 2026, arritën në rreth 48.1 miliardë lekë."
    },
    {
        "url": "https://financa.gov.al/newsroom/permbledhje-e-performances-paraprake-te-te-ardhurave-dhe-shpenzimeve-per-periudhen-12-mujore-2025/",
        "title": "Përmbledhje e Performancës Paraprake të të Ardhurave dhe Shpenzimeve për periudhën 12 mujore 2025",
        "publish_time": "2026-03-03",
        "content": "Performanca paraprake e treguesve fiskalë të konsoliduar për periudhën Janar-Dhjetor 2025 reflekton ecurinë e mbledhjes së të ardhurave dhe realizimit të shpenzimeve. Të ardhurat totale, për 12 mujorin e vitit 2025, arritën në rreth 754.6 miliardë lekë. Shpenzimet e përgjithshme publike, për periudhën 12 mujore të vitit 2025, arritën në rreth 801.7 miliardë lekë."
    },
    {
        "url": "https://financa.gov.al/newsroom/zhvillohet-ankandi-rihapje-obligacione-20-vjecare-kerkese-e-larte-nga-tregu/",
        "title": "Zhvillohet ankandi rihapje obligacione 20-vjeçare, kërkesë e lartë nga tregu",
        "publish_time": "2026-03-02",
        "content": "Ministria e Financave shënoi një tjetër sukses të rëndësishëm në tregun e brendshëm të titujve qeveritarë, duke zhvilluar më 2 mars 2026 ankandin rihapje obligacione 20-vjeçare. Me një shumë të shpallur prej 1 miliardë lekësh dhe kërkesa që arritën në 2.60 miliardë lekë, ky ankand u mbulua 2.60 herë."
    },
    {
        "url": "https://financa.gov.al/newsroom/ministri-petrit-malaj-vizite-zyrtare-ne-poloni-takohet-me-ministrin-e-financave-dhe-ekonomise-dhe-drejtues-te-bank-gospodarstwa-krajowego/",
        "title": "Ministri Petrit Malaj, vizitë zyrtare në Poloni, takohet me Ministrin e Financave dhe Ekonomisë dhe drejtues të Bank Gospodarstwa Krajowego",
        "publish_time": "2026-02-23",
        "content": "Ministri i Financave, z. Petrit Malaj, ndodhet sot në Poloni, së bashku me Ministren e Ekonomisë dhe Inovacionit, znj. Delina Ibrahimaj, në kuadrin e një vizite zyrtare. Gjatë kësaj vizite, Ministri z. Petrit Malaj zhvilloi një takim me Ministrin e Financave dhe Ekonomisë të Polonisë, z. Andrzej Domański."
    },
    {
        "url": "https://financa.gov.al/newsroom/ministria-e-financave-transferohen-rreth-167-milione-euro-ne-fondin-e-vecante-te-pensioneve/",
        "title": "Ministria e Financave, transferohen rreth 167 milionë euro në Fondin e Veçantë të Pensioneve",
        "publish_time": "2026-02-20",
        "content": "Ministria e Financave njofton se të gjitha fondet buxhetore që nuk u shpenzuan nga ministritë dhe institucionet publike gjatë vitit 2025 tashmë janë transferuar në Fondin e Veçantë të Pensioneve. Shuma përkatëse është rreth 167 milionë euro."
    },
    {
        "url": "https://financa.gov.al/newsroom/ministri-i-financave-petrit-malaj-takohet-me-ministrin-e-deleguar-per-tregtine-e-jashtme-dhe-atraktivitetin-ekonomik-te-frances-z-nicolas-forissier/",
        "title": "Ministri i Financave, Petrit Malaj takohet me Ministrin e Deleguar për Tregtinë e Jashtme dhe Atraktivitetin Ekonomik të Francës, z. Nicolas Forissier",
        "publish_time": "2026-02-19",
        "content": "Ministri i Financave, z. Petrit Malaj, zhvilloi një takim zyrtar me Ministrin e Deleguar për Tregtinë e Jashtme dhe Atraktivitetin Ekonomik të qeverisë së Francës, z. Nicolas Forissier. Palët diskutuan mbi integrimin evropian, zhvillimin e qëndrueshëm dhe nxitjen e investimeve dypalëshe."
    },
    {
        "url": "https://financa.gov.al/newsroom/ministri-i-financave-takohet-me-drejtorin-global-te-grupit-te-bankes-boterore-per-zhvillimin-urban-financat-vendore-turizmin/",
        "title": "Ministri i Financave takohet me Drejtorin Global të Grupit të Bankës Botërore për Zhvillimin Urban, Financat Vendore, Turizmin",
        "publish_time": "2026-02-12",
        "content": "Ministri i Financave, z. Petrit Malaj, zhvilloi një takim Drejtorin Global të Grupit të Bankës Botërore për Zhvillimin Urban, Financat Vendore, Turizmin dhe Menaxhimin e Fatkeqësive, z.Ming Zhang. Takimi u fokusua në zgjerimin e portofolit investues dhe rolin e turizmit në rritjen ekonomike."
    },
    {
        "url": "https://financa.gov.al/newsroom/ministria-e-financave-organizon-nje-takim-me-bankat-tregtare-skema-e-garancise-sovrane-per-sektorin-bujqesor-rishikim-i-progresit-dhe-perspektiva-e-ardhshme/",
        "title": "Ministria e Financave organizon një takim me bankat tregtare – “Skema e Garancisë Sovrane për Sektorin Bujqësor – Rishikim i Progresit dhe Perspektiva e Ardhshme”",
        "publish_time": "2026-02-11",
        "content": "Ministria e Financave organizoi një takim të zgjeruar mbi përdorimin e Skemës së Garancisë Sovrane dhe Programit të Financimit të Biznesit Mikro, të Vogël dhe të Mesëm (PFBVM). Takimi u zhvillua me pjesëmarrjen e Guvernatorit të Bankës së Shqipërisë dhe Ministrit të Bujqësisë."
    },
    {
        "url": "https://financa.gov.al/newsroom/ministri-i-financave-prezanton-drejtori-i-ri-te-pergjithshem-te-doganave-z-besmir-beja/",
        "title": "Ministri i Financave prezanton Drejtori i ri të Përgjithshëm të Doganave, z. Besmir Beja",
        "publish_time": "2026-02-02",
        "content": "Ministri i Financave, z. Petrit Malaj, prezantoi sot Drejtorin e ri të Përgjithshëm të Doganave, z. Besmir Beja, i cili merr detyrën duke zëvendësuar z. Gent Gazheli. Prioritetet kryesore do të jenë sistemet inteligjente, teknologjitë moderne dhe lufta ndaj informalitetit."
    },
    {
        "url": "https://financa.gov.al/newsroom/zhvillohet-ankandi-i-instrumentit-obligacione-15-vjecare-kerkese-e-larte-nga-tregu/",
        "title": "Zhvillohet ankandi i instrumentit obligacione 15-vjeçare, kërkesë e lartë nga tregu",
        "publish_time": "2026-02-02",
        "content": "Ministria e Financave shënoi një tjetër sukses të rëndësishëm në tregun e brendshëm të titujve qeveritarë, duke zhvilluar më 2 shkurt 2026 ankandin për obligacionet 15-vjeçare. Me një shumë të shpallur prej 2 miliardë lekësh dhe kërkesa që arritën në 6.05 miliardë lekë, ky ankand u mbulua 3.02 herë."
    },
    {
        "url": "https://financa.gov.al/newsroom/ministri-i-financave-petrit-malaj-merr-pjese-ne-degjesen-me-fermeret-ne-divjake-per-skemen-kombetare-2026/",
        "title": "Ministri i Financave, Petrit Malaj, merr pjesë në dëgjesën me fermerët në Divjakë për Skemën Kombëtare 2026",
        "publish_time": "2026-01-30",
        "content": "Ministri i Financave, Petrit Malaj, ka parë nga afër punën në terren të strukturave të Ministrisë së Financave, duke marrë pjesë në një dëgjesë me fermerët në Divjakë, për të diskutuar Skemën Kombëtare të Mbështetjes. Bujqësia është një nga shtyllat e ekonomisë sonë dhe mbështetja për fermerët është prioritet i yni."
    },
    {
        "url": "https://financa.gov.al/newsroom/fjala-e-ministrit-petrit-malaj-ne-kuvend-akti-normativ-nr-11-per-buxhetin-e-vitit-2025/",
        "title": "Fjala e Ministrit Petrit Malaj në Kuvend- Akti Normativ nr. 11 për Buxhetin e vitit 2025",
        "publish_time": "2026-01-27",
        "content": "Ministri i Financave, Petrit Malaj, prezantoi në Kuvend Aktin Normativ nr. 11 për Buxhetin e Vitit 2025. Gjatë fjalës së tij, Malaj theksoi se ky akt synon rishpërndarjen e fondeve për të mbështetur projektet prioritare dhe për të garantuar qëndrueshmërinë fiskale."
    },
    {
        "url": "https://financa.gov.al/newsroom/ministri-i-financave-dhe-drejtori-i-pergjithshem-i-doganave-vizitojne-dy-kompani-perfituese-te-statusit-operator-ekonomik-i-autorizuar/",
        "title": "Ministri i Financave dhe Drejtori i Përgjithshëm i Doganave vizitojnë dy kompani përfituese të statusit Operator Ekonomik i Autorizuar",
        "publish_time": "2026-01-24",
        "content": "Ministri i Financave dhe Drejtori i Përgjithshëm i Doganave vizituan dy kompani që kanë përfituar statusin e Operatorit Ekonomik të Autorizuar (OEA). Ky status u ofron bizneseve lehtësi në procedurat doganore dhe rrit konkurrueshmërinë e tyre në tregun ndërkombëtar."
    },
    {
        "url": "https://financa.gov.al/newsroom/miratohet-kuadri-makroekonomik-dhe-fiskal-per-periudhen-2027-2029/",
        "title": "Miratohet Kuadri Makroekonomik dhe Fiskal për periudhën 2027–2029",
        "publish_time": "2026-01-22",
        "content": "Qeveria ka miratuar Kuadrin Makroekonomik dhe Fiskal për periudhën 2027-2029. Ky dokument përcakton objektivat kryesorë të politikës ekonomike dhe fiskale për vitet në vijim, duke synuar një rritje të qëndrueshme ekonomike dhe ulje të mëtejshme të borxhit publik."
    },
    {
        "url": "https://financa.gov.al/newsroom/ministri-petrit-malaj-prezanton-ne-komisionin-per-ceshtjet-ligjore-dhe-administraten-publike-aktin-normativ-nr-11-per-buxhetin-e-vitit-2025/",
        "title": "Ministri Petrit Malaj prezanton në komisionin për Çështjet Ligjore dhe Administratën Publike Aktin Normativ Nr.11 për Buxhetin e vitit 2025",
        "publish_time": "2026-01-20",
        "content": "Ministri Petrit Malaj prezantoi në Komisionin për Çështjet Ligjore dhe Administratën Publike Aktin Normativ nr. 11 për Buxhetin e Vitit 2025. Ai shpjegoi arsyet e ndryshimeve të propozuara dhe ndikimin e tyre në financat publike."
    },
    {
        "url": "https://financa.gov.al/newsroom/ministri-malaj-merr-pjese-ne-mbledhjen-e-komitetit-te-perbashket-ekzekutiv-per-kuadrin-e-bashkepunimit-mes-qeverise-se-shqiperise-dhe-kombeve-te-bashkuara/",
        "title": "Ministri Malaj merr pjesë në mbledhjen e Komitetit të Përbashkët Ekzekutiv për kuadrin e bashkëpunimit mes Qeverisë së Shqipërisë dhe Kombeve të Bashkuara",
        "publish_time": "2026-01-15",
        "content": "Ministri Malaj mori pjesë në mbledhjen e Komitetit të Përbashkët Ekzekutiv për Kuadrin e Bashkëpunimit mes Qeverisë së Shqipërisë dhe Kombeve të Bashkuara. Gjatë takimit u diskutua mbi ecurinë e projekteve të përbashkëta dhe harmonizimin e prioriteteve zhvillimore."
    },
    {
        "url": "https://financa.gov.al/newsroom/komiteti-nderministror-i-emergjencave-civile/",
        "title": "Komiteti Ndërministror i Emergjencave Civile",
        "publish_time": "2026-01-09",
        "content": "U mblodh Komiteti Ndërministror i Emergjencave Civile për të diskutuar masat e marra për përballimin e situatave të mundshme emergjente. Pjesëmarresit raportuan mbi gadishmërinë e strukturave dhe koordinimin ndërmjet institucioneve."
    },
    {
        "url": "https://financa.gov.al/newsroom/ministri-petrit-malaj-zhvillon-nje-takim-me-drejtues-te-administrates-tatimore-dhe-doganore/",
        "title": "Ministri Petrit Malaj zhvillon një takim me drejtues të Administratës Tatimore dhe Doganore",
        "publish_time": "2026-01-08",
        "content": "Ministri Petrit Malaj zhvilloi një takim pune me drejtuesit e administratës tatimore dhe doganore. Takimi u fokusua në analizën e treguesve të mbledhjes së të ardhurave për pjesën e parë të vitit dhe objektivat për muajin në vijim."
    },
    {
        "url": "https://financa.gov.al/newsroom/zhvillohet-ankandi-i-instrumentit-obligacione-20-vjecare-kerkese-e-larte-nga-tregu/",
        "title": "Zhvillohet ankandi i instrumentit obligacione 20-vjeçare, kërkesë e lartë nga tregu",
        "publish_time": "2026-01-06",
        "content": "Ministria e Financave zhvilloi me sukses ankandin e instrumentit obligacione 20-vjeçare, i cili shënoi një kërkesë të lartë nga tregu. Ky instrument afatgjatë shërben si një referencë e rëndësishme për tregun e kapitaleve."
    }
]

def insert():
    conn = get_conn()
    cur = conn.cursor()
    count = 0
    for art in articles:
        try:
            cur.execute("""
                INSERT INTO alb_financa (url, title, content, publish_time, author, language)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (url) DO UPDATE SET 
                    content = EXCLUDED.content,
                    title = EXCLUDED.title;
            """, (art['url'], art['title'], art['content'], art['publish_time'], 'Ministria e Financave', 'sq'))
            count += 1
        except Exception as e:
            print(f"Error inserting {art['url']}: {e}")
            conn.rollback()
    conn.commit()
    cur.close()
    conn.close()
    print(f"Successfully inserted/updated {count} articles.")

if __name__ == "__main__":
    insert()
