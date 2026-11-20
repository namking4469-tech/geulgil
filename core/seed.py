"""공모전·에이전시·출판사·플랫폼 기초 데이터.
주의: 마감일·상금·투고 방침은 해마다 바뀐다. 여기에는 '통상 시기'와 공식 사이트만 담고,
정확한 요강은 반드시 공식 사이트에서 확인하도록 화면에 안내한다. 이메일은 넣지 않는다(사용자가 확인 후 입력)."""
from sqlalchemy import select, func

CONTESTS = [
    # name, organizer, country, genres, length, period, prize, eligibility, url
    ("조선일보 신춘문예", "조선일보", "한국", ["순문학", "시", "아동/동화", "희곡/시나리오", "평론"], "부문별 상이(단편소설 원고지 80매 안팎)", "매년 11월 공고 · 12월 초 마감", "부문별 상이", "미등단 신인", "https://www.chosun.com"),
    ("동아일보 신춘문예", "동아일보", "한국", ["순문학", "시", "아동/동화", "희곡/시나리오", "평론"], "부문별 상이(중편·단편 등)", "매년 11월 공고 · 12월 초 마감", "부문별 상이", "미등단 신인", "https://www.donga.com"),
    ("한국일보 신춘문예", "한국일보", "한국", ["순문학", "시", "아동/동화", "희곡/시나리오"], "부문별 상이", "매년 11월 공고 · 12월 초 마감", "부문별 상이", "미등단 신인", "https://www.hankookilbo.com"),
    ("경향신문 신춘문예", "경향신문", "한국", ["순문학", "시", "평론"], "부문별 상이", "매년 11월 공고 · 12월 초 마감", "부문별 상이", "미등단 신인", "https://www.khan.co.kr"),
    ("서울신문 신춘문예", "서울신문", "한국", ["순문학", "시", "아동/동화", "희곡/시나리오", "평론"], "부문별 상이", "매년 11월 공고 · 12월 초 마감", "부문별 상이", "미등단 신인", "https://www.seoul.co.kr"),
    ("문학동네 신인상", "문학동네", "한국", ["순문학", "시", "평론"], "부문별 상이", "연 1회(공식 공고 확인)", "부문별 상이", "신인", "https://www.munhak.com"),
    ("창비신인문학상", "창비", "한국", ["순문학", "시", "평론"], "부문별 상이", "연 1회(통상 상반기 마감)", "부문별 상이", "신인", "https://www.changbi.com"),
    ("한겨레문학상", "한겨레신문사", "한국", ["순문학"], "장편소설", "연 1회(통상 봄 마감)", "공식 공고 확인", "기성·신인 무관", "https://www.hani.co.kr"),
    ("문학과사회 신인문학상", "문학과지성사", "한국", ["순문학", "시", "평론"], "부문별 상이", "연 1회(공식 공고 확인)", "부문별 상이", "신인", "https://moonji.com"),
    ("현대문학 신인추천", "현대문학", "한국", ["순문학", "시", "평론"], "부문별 상이", "연 1회(공식 공고 확인)", "부문별 상이", "신인", "https://www.hdmh.co.kr"),
    ("교보문고 스토리대상", "교보문고", "한국", ["로맨스", "판타지", "SF", "미스터리/스릴러", "순문학"], "중·장편 및 단편 부문", "연 1회(통상 여름 접수)", "공식 공고 확인", "제한 없음", "https://www.kyobobook.co.kr"),
    ("브런치북 출판 프로젝트", "카카오 브런치스토리", "한국", ["수필/에세이", "논픽션", "순문학"], "브런치북 1권", "연 1회(통상 가을 접수)", "출간 지원 및 상금", "브런치 작가", "https://brunch.co.kr"),
    ("대한민국 스토리 공모대전", "한국콘텐츠진흥원", "한국", ["희곡/시나리오", "판타지", "SF", "미스터리/스릴러"], "원천 스토리(공식 양식)", "연 1회(공식 공고 확인)", "공식 공고 확인", "제한 없음", "https://www.kocca.kr"),
    ("수림문학상", "수림문화재단 · 연합뉴스", "한국", ["순문학"], "장편소설", "연 1회(공식 공고 확인)", "공식 공고 확인", "신인·등단 10년 이내 등(요강 확인)", "https://www.surimcf.or.kr"),
    ("문피아 지상최대공모전", "문피아", "한국", ["판타지", "무협", "로맨스", "SF"], "웹소설 연재", "연 1회(통상 봄~여름)", "공식 공고 확인", "제한 없음", "https://www.munpia.com"),
    ("Commonwealth Short Story Prize", "Commonwealth Foundation", "국제(영연방)", ["순문학"], "단편 2,000~5,000 단어", "통상 9월~11월 접수", "지역상·대상 상금", "영연방 국가 시민", "https://commonwealthfoundation.com"),
    ("Bridport Prize", "Bridport Arts Centre", "영국(국제 접수)", ["순문학", "시"], "단편·시·플래시픽션·장편 부문", "통상 5월 말 마감", "부문별 상금", "제한 없음(영어 작품)", "https://www.bridportprize.org.uk"),
    ("The Bath Novel Award", "The Bath Novel Awards", "영국(국제 접수)", ["순문학", "청소년"], "장편소설(미출간·미계약)", "통상 봄 마감", "상금 및 에이전트 소개", "제한 없음(영어 작품)", "https://bathnovelaward.co.uk"),
    ("Writers of the Future", "Author Services", "미국(국제 접수)", ["SF", "판타지"], "단편·중편", "분기별 접수(연 4회)", "분기 상금 및 연간 대상", "프로 데뷔 전 작가", "https://www.writersofthefuture.com"),
    ("Montreal International Poetry Prize", "Montreal Prize", "캐나다(국제 접수)", ["시"], "시 1편(행 수 제한)", "격년·공식 공고 확인", "공식 공고 확인", "제한 없음(영어 작품)", "https://www.montrealpoetryprize.com"),
    ("The Moth Poetry Prize", "The Moth Magazine", "아일랜드(국제 접수)", ["시"], "미발표 시 1편", "통상 12월 말 마감", "공식 공고 확인", "제한 없음(영어 작품)", "https://www.themothmagazine.com"),
    ("GKL 한국문학번역상 / 번역신인상", "한국문학번역원", "한국", ["순문학", "시"], "지정 작품 번역", "연 1회(공식 공고 확인)", "공식 공고 확인", "번역가·신인 번역가", "https://www.ltikorea.or.kr"),
]

DIRECTORY = [
    # kind, name, country, genres, accepts, url, note
    ("에이전시", "KL Management", "한국", ["순문학"], "공식 사이트 확인", "http://www.klmanagement.co.kr", "한국문학의 해외 판권 수출을 전문으로 하는 에이전시."),
    ("에이전시", "Barbara J. Zitwer Agency", "미국", ["순문학"], "공식 사이트 확인", "https://www.barbarajzitweragency.com", "한국문학을 해외에 다수 소개해 온 뉴욕 기반 에이전시."),
    ("에이전시", "에릭양 에이전시 (Eric Yang Agency)", "한국", ["순문학", "논픽션"], "공식 사이트 확인", "https://www.eyagency.com", "국내외 판권 중개."),
    ("에이전시", "임프리마 코리아 (Imprima Korea)", "한국", ["순문학", "논픽션", "아동/동화"], "공식 사이트 확인", "http://www.imprima.co.kr", "국내외 판권 중개."),
    ("에이전시", "BC 에이전시", "한국", ["순문학", "논픽션", "아동/동화"], "공식 사이트 확인", "http://www.bcagency.co.kr", "국내외 판권 중개."),
    ("에이전시", "Curtis Brown", "영국", ["순문학", "미스터리/스릴러", "논픽션"], "온라인 투고 포털(영어 원고)", "https://www.curtisbrown.co.uk", "영국의 대형 문학 에이전시. 에이전트별 투고 지침 확인."),
    ("에이전시", "Writers House", "미국", ["순문학", "청소년", "아동/동화"], "에이전트별 쿼리(영어)", "https://www.writershouse.com", "미국의 대형 문학 에이전시."),
    ("에이전시", "Janklow & Nesbit Associates", "미국/영국", ["순문학", "논픽션"], "쿼리 레터(영어)", "https://www.janklowandnesbit.com", ""),
    ("에이전시", "Aitken Alexander Associates", "영국", ["순문학", "논픽션"], "투고 지침 확인", "https://aitkenalexander.co.uk", ""),
    ("에이전시", "RCW Literary Agency", "영국", ["순문학", "논픽션"], "투고 지침 확인", "https://www.rcwlitagency.com", ""),
    ("에이전시", "Trident Media Group", "미국", ["순문학", "로맨스", "SF", "판타지", "미스터리/스릴러"], "온라인 쿼리 양식", "https://www.tridentmediagroup.com", ""),
    ("에이전시", "Andrew Nurnberg Associates", "영국", ["순문학", "아동/동화"], "투고 지침 확인", "https://www.andrewnurnberg.com", "번역 판권에 강한 국제 에이전시."),
    ("출판사", "문학동네", "한국", ["순문학", "시", "수필/에세이"], "투고 안내 확인", "https://www.munhak.com", ""),
    ("출판사", "창비", "한국", ["순문학", "시", "아동/동화", "청소년"], "투고 안내 확인", "https://www.changbi.com", ""),
    ("출판사", "민음사", "한국", ["순문학", "시", "논픽션"], "투고 안내 확인", "https://minumsa.com", ""),
    ("출판사", "문학과지성사", "한국", ["순문학", "시", "평론"], "투고 안내 확인", "https://moonji.com", ""),
    ("출판사", "은행나무", "한국", ["순문학", "수필/에세이"], "투고 안내 확인", "https://ehbook.co.kr", ""),
    ("출판사", "자음과모음", "한국", ["순문학", "청소년", "SF"], "투고 안내 확인", "https://jamo21.net", ""),
    ("출판사", "Tilted Axis Press", "영국", ["순문학"], "투고 기간 한정(공지 확인)", "https://www.tiltedaxispress.com", "아시아 문학 번역 전문 독립 출판사."),
    ("출판사", "Honford Star", "영국", ["순문학", "SF"], "공식 사이트 확인", "https://www.honfordstar.com", "동아시아 문학 번역 출판."),
    ("출판사", "Deep Vellum", "미국", ["순문학", "시"], "투고 지침 확인", "https://www.deepvellum.org", "번역문학 중심 비영리 출판사."),
    ("출판사", "And Other Stories", "영국", ["순문학"], "투고 지침 확인", "https://www.andotherstories.org", ""),
    ("출판사", "Graywolf Press", "미국", ["순문학", "시", "논픽션"], "투고 기간 한정(공지 확인)", "https://www.graywolfpress.org", ""),
    ("출판사", "Penguin Random House", "미국/국제", ["순문학", "논픽션", "아동/동화"], "대부분 에이전트 경유만 접수", "https://www.penguinrandomhouse.com", "대형 출판그룹. 직접 투고는 대부분 받지 않음."),
    ("출판사", "HarperCollins", "미국/국제", ["순문학", "로맨스", "논픽션"], "대부분 에이전트 경유(일부 임프린트 공개 투고)", "https://www.harpercollins.com", ""),
    ("플랫폼", "Amazon Kindle Direct Publishing (KDP)", "국제", [], "자가출판(EPUB 업로드)", "https://kdp.amazon.com", "전자책·POD 자가출판. EPUB 을 그대로 올릴 수 있음."),
    ("플랫폼", "Kobo Writing Life", "국제", [], "자가출판(EPUB 업로드)", "https://www.kobo.com/writinglife", ""),
    ("플랫폼", "Apple Books for Authors", "국제", [], "자가출판(EPUB 업로드)", "https://authors.apple.com", ""),
    ("플랫폼", "Google Play Books 파트너 센터", "국제", [], "자가출판(EPUB/PDF 업로드)", "https://play.google.com/books/publish", ""),
    ("플랫폼", "Draft2Digital", "국제", [], "여러 서점 일괄 배포", "https://www.draft2digital.com", "하나의 원고를 여러 전자책 서점에 배포."),
    ("플랫폼", "리디", "한국", ["로맨스", "판타지", "순문학"], "출판사·CP 경유 또는 제휴 문의", "https://ridibooks.com", ""),
    ("플랫폼", "밀리의서재", "한국", [], "밀리로드 연재 / 출판사 경유", "https://www.millie.co.kr", ""),
    ("플랫폼", "교보문고 퍼플(POD)", "한국", [], "자가출판(POD·전자책)", "https://www.kyobobook.co.kr", ""),
    ("플랫폼", "부크크", "한국", [], "자가출판(POD·전자책, ISBN 대행)", "https://bookk.co.kr", "ISBN 발급을 대행해 주는 자가출판 플랫폼."),
    ("플랫폼", "유페이퍼", "한국", [], "전자책 자가출판·유통", "https://www.upaper.kr", ""),
    ("플랫폼", "브런치스토리", "한국", ["수필/에세이"], "작가 신청 후 연재", "https://brunch.co.kr", ""),
    ("플랫폼", "카카오페이지", "한국", ["로맨스", "판타지", "무협"], "CP·출판사 경유 / 스테이지 연재", "https://page.kakao.com", ""),
    ("플랫폼", "네이버 시리즈 / 챌린지리그", "한국", ["로맨스", "판타지", "무협"], "챌린지리그 자유 연재", "https://novel.naver.com", ""),
    ("플랫폼", "문피아", "한국", ["판타지", "무협"], "자유 연재", "https://www.munpia.com", ""),
    ("플랫폼", "Wattpad", "국제", ["로맨스", "판타지", "청소년"], "자유 연재", "https://www.wattpad.com", ""),
    ("플랫폼", "Royal Road", "국제", ["판타지", "SF"], "자유 연재(영어)", "https://www.royalroad.com", ""),
    ("플랫폼", "Tapas", "국제", ["로맨스", "판타지"], "자유 연재(영어)", "https://tapas.io", ""),
    ("지원기관", "한국문학번역원 (LTI Korea)", "한국", ["순문학", "시"], "번역·출판 지원사업 공모", "https://www.ltikorea.or.kr", "한국문학 번역·해외 출판 지원."),
    ("지원기관", "한국문화예술위원회 (ARKO)", "한국", [], "창작 지원사업 공모", "https://www.arko.or.kr", "문학 창작기금·발표지원 등."),
    ("지원기관", "한국출판문화산업진흥원", "한국", [], "출판 지원사업 공모", "https://www.kpipa.or.kr", "우수출판콘텐츠 제작 지원 등."),
    ("지원기관", "국립중앙도서관 ISBN·ISSN·납본시스템", "한국", [], "ISBN 신청", "https://www.nl.go.kr/seoji/", "ISBN 발급 신청 공식 창구."),
    ("지원기관", "한국저작권위원회 저작권 등록", "한국", [], "저작권 등록", "https://www.cros.or.kr", ""),
    ("지원기관", "QueryTracker", "미국", [], "에이전트 검색·투고 추적", "https://querytracker.net", "영미권 에이전트 검색 서비스."),
    ("지원기관", "Poets & Writers", "미국", [], "공모전·에이전트·문예지 DB", "https://www.pw.org", ""),
    ("지원기관", "Reedsy", "국제", [], "편집자·디자이너·번역가 마켓", "https://reedsy.com", ""),
]


def seed(Session):
    from .db import Contest, DirEntry
    with Session() as s:
        if not s.scalar(select(func.count()).select_from(Contest)):
            for n, o, c, g, ln, p, pr, e, u in CONTESTS:
                s.add(Contest(name=n, organizer=o, country=c, genres=g, length=ln, period=p, prize=pr,
                              eligibility=e, url=u))
        if not s.scalar(select(func.count()).select_from(DirEntry)):
            for k, n, c, g, a, u, note in DIRECTORY:
                s.add(DirEntry(kind=k, name=n, country=c, genres=g, accepts=a, url=u, note=note))
        s.commit()
