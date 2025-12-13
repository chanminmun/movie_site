from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
import re
import requests
from django.conf import settings
from django.shortcuts import render,redirect,get_object_or_404
from django.contrib import messages
from .forms import CommentForm
from .models import Comment
from .models import Comment, Favorite
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Count
# -----------------------------
# 공통 상수/헬퍼
# -----------------------------
TMDB_BASE = "https://api.themoviedb.org/3"
IMG = "https://image.tmdb.org/t/p"

def _auth_headers():
    """TMDB Bearer 토큰 헤더 생성"""
    return {
        "accept": "application/json",
        "Authorization": f"Bearer {settings.TMDB_BEARER_TOKEN}",
    }

def _img_url(path, size='w500', fallback='/static/assets/images/default-movie.jpg'):
    """TMDB 이미지 경로 헬퍼 (size: w200/w300/w500/w780/w1280 등)"""
    if path:
        return f"{IMG}/{size}{path}"
    return fallback


# -----------------------------
# index: KOBIS 박스오피스 + TMDB 포스터 매핑
# -----------------------------
def index(request):
    KOBIS_API_KEY = settings.KOBIS_API_KEY
    tmdb_token = settings.TMDB_BEARER_TOKEN

    # 박스오피스는 "전날" 기준
    target_date = (datetime.today() - timedelta(days=1)).strftime("%Y%m%d")
    kobis_url = (
        "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/"
        f"searchDailyBoxOfficeList.json?key={KOBIS_API_KEY}&targetDt={target_date}"
    )
    kobis_data = requests.get(kobis_url, timeout=10).json()
    movies = kobis_data["boxOfficeResult"]["dailyBoxOfficeList"]

    headers = {
        "accept": "application/json",
        "Authorization": f"Bearer {tmdb_token}",
    }

    for movie in movies:
        title = movie["movieNm"]

        # 1) TMDB에서 영화 기본 정보 검색
        tmdb_url = f"{TMDB_BASE}/search/movie"
        resp = requests.get(
            tmdb_url,
            headers=headers,
            params={"query": title, "language": "ko-KR"},
            timeout=10,
        )
        data = resp.json()

        if data.get("results"):
            top = data["results"][0]
            tmdb_id = top.get("id")
            tmdb_vote = top.get("vote_average") or 0.0

            movie["poster_url"] = _img_url(top.get("poster_path"), size="w500")
            movie["tmdb_id"] = tmdb_id          # 상세 페이지 링크에 사용
            movie["tmdb_vote"] = tmdb_vote      # TMDB 실제 별점
        else:
            movie["poster_url"] = "/static/assets/images/default-movie.jpg"
            movie["tmdb_id"] = None
            movie["tmdb_vote"] = None

        # 2) 기본값 세팅 (사용자 평점 관련)
        movie["user_rating"] = None       # 사용자 평균 평점 (1~10)
        movie["rating_count"] = 0         # 평점 남긴 사람 수
        movie["rating_status"] = None     # 'fair' / 'over' / 'under'

        # 3) tmdb_id 가 있는 영화에 대해서만 댓글 기반 사용자 평점 계산
        if movie["tmdb_id"] is not None:
            stats = Comment.objects.filter(
                movie_tmdb_id=movie["tmdb_id"]
            ).aggregate(
                avg=Avg("rating"),
                cnt=Count("rating"),
            )

            avg_rating = stats["avg"]
            cnt_rating = stats["cnt"] or 0

            movie["rating_count"] = cnt_rating

            # 댓글이 하나도 없으면 그냥 None 으로 둠
            if avg_rating is not None and cnt_rating > 0 and movie["tmdb_vote"]:
                movie["user_rating"] = float(avg_rating)

                # 4) TMDB 실제 별점 vs 사용자 평균 평점 비교
                # diff = 사용자평점 - TMDB별점
                diff = movie["user_rating"] - movie["tmdb_vote"]

                # 네가 말한 기준:
                # - |diff| < 2         -> 적절한 평가
                # - diff <= -2         -> 고평가 (사용자 평점이 2 이상 낮음)
                # - diff >=  2         -> 저평가 (사용자 평점이 2 이상 높음)
                if diff <= -2:
                    movie["rating_status"] = "over"     # 고평가
                elif diff >= 2:
                    movie["rating_status"] = "under"    # 저평가
                else:
                    movie["rating_status"] = "fair"     # 적절한 평가

    return render(request, "index.html", {
        "movies": movies,
        "date": target_date,
    })

# -----------------------------
# browse: 트렌딩/장르/감독
# -----------------------------
def browse(request):
    tmdb_token = settings.TMDB_BEARER_TOKEN
    debug = []

    if not tmdb_token:
        debug.append("TMDB 토큰이 설정되지 않았습니다. settings.TMDB_BEARER_TOKEN 확인.")
        return render(request, "browse.html", {
            "featured_movies": [],
            "top_genres": [],
            "popular_directors": [],
            "tmdb_error": "\n".join(debug),
        })

    headers = _auth_headers()

    def poster_url(path):
        return _img_url(path, size="w500")

    # A) Featured (Trending)
    featured_movies = []
    try:
        r = requests.get(f"{TMDB_BASE}/trending/movie/week",
                         headers=headers, params={"language": "ko-KR"}, timeout=10)
        r.raise_for_status()
        items = r.json().get("results", [])
        debug.append(f"Trending 응답 수: {len(items)}")
        for m in items[:9]:
            featured_movies.append({
                "title": m.get("title") or m.get("name"),
                "vote": m.get("vote_average", 0.0),
                "popularity": int(m.get("popularity", 0)),
                "poster_url": poster_url(m.get("poster_path")),
                "id": m.get("id"),
            })
    except Exception as e:
        debug.append(f"Trending 실패: {type(e).__name__} - {e}")

    # B) Top genres (popular에서 가장 자주 등장하는 장르)
    top_genres = []
    try:
        gr = requests.get(f"{TMDB_BASE}/genre/movie/list",
                          headers=headers, params={"language": "ko-KR"}, timeout=10)
        gr.raise_for_status()
        genre_map = {g["id"]: g["name"] for g in gr.json().get("genres", [])}
        debug.append(f"장르 수: {len(genre_map)}")

        pr = requests.get(f"{TMDB_BASE}/movie/popular",
                          headers=headers, params={"language": "ko-KR", "page": 1}, timeout=10)
        pr.raise_for_status()
        popular = pr.json().get("results", [])
        debug.append(f"Popular 응답 수: {len(popular)}")

        from collections import Counter
        genre_counter = Counter()
        for m in popular:
            for gid in m.get("genre_ids", []):
                genre_counter[gid] += 1

        top_genre_ids = [gid for gid, _ in genre_counter.most_common(3)]
        debug.append(f"Top 장르 IDs: {top_genre_ids}")

        for gid in top_genre_ids:
            rep = next((m for m in popular if gid in m.get("genre_ids", [])), None)
            if rep:
                top_genres.append({
                    "genre_name": genre_map.get(gid, "기타"),
                    "title": rep.get("title"),
                    "vote": rep.get("vote_average", 0.0),
                    "popularity": int(rep.get("popularity", 0)),
                    "poster_url": poster_url(rep.get("poster_path")),
                })
    except Exception as e:
        debug.append(f"Top genres 실패: {type(e).__name__} - {e}")

    # C) Directors (trending person 중 directing)
    popular_directors = []
    try:
        rr = requests.get(f"{TMDB_BASE}/trending/person/week",
                          headers=headers, params={"language": "ko-KR"}, timeout=10)
        rr.raise_for_status()
        people = rr.json().get("results", [])
        debug.append(f"Trending person 응답 수: {len(people)}")

        for p in people:
            if (p.get("known_for_department") or "").lower() == "directing":
                known_for = p.get("known_for", [])
                top_work = None
                for k in known_for:
                    top_work = k.get("title") or k.get("name")
                    if top_work:
                        break
                popular_directors.append({
                    "name": p.get("name"),
                    "profile_url": poster_url(p.get("profile_path")),
                    "top_work": top_work or "대표작 정보 없음",
                    "popularity": int(p.get("popularity", 0)),
                })
            if len(popular_directors) >= 4:
                break
        debug.append(f"감독 추출 수: {len(popular_directors)}")
    except Exception as e:
        debug.append(f"Directors 실패: {type(e).__name__} - {e}")

    return render(request, "browse.html", {
        "featured_movies": featured_movies,
        "top_genres": top_genres,
        "popular_directors": popular_directors,
        "tmdb_error": "\n".join(debug),
    })


# -----------------------------
# movie_list: 정렬 스위치 (boxoffice / recent / rating)
# -----------------------------
def _tmdb_search_one(headers: dict, title: str, year: str | None = None):
    params = {
        "query": title,
        "language": "ko-KR",
        "include_adult": "false",
        "region": "KR",
    }
    if year:
        params["year"] = year
    r = requests.get(f"{TMDB_BASE}/search/movie", headers=headers, params=params, timeout=10)
    r.raise_for_status()
    results = r.json().get("results", [])
    return results[0] if results else None

def movie_list(request):
    tmdb_token = getattr(settings, 'TMDB_BEARER_TOKEN', None)
    kobis_key  = getattr(settings, 'KOBIS_KEY', None)

    if not tmdb_token:
        return render(request, "movie_list.html", {
            "movies": [],
            "tmdb_error": "TMDB 토큰이 설정되지 않았습니다. settings.TMDB_BEARER_TOKEN를 확인하세요.",
        })

    headers = _auth_headers()
    sort = request.GET.get("sort", "boxoffice")

    movies = []
    tmdb_error = ""

    try:
        if not kobis_key:
            raise RuntimeError("KOBIS 키가 없습니다. settings.KOBIS_KEY를 설정하세요.")

        today_kr = datetime.now(ZoneInfo("Asia/Seoul")).date()
        target_date = (today_kr - timedelta(days=1)).strftime("%Y%m%d")

        kobis_url = (
            "https://www.kobis.or.kr/kobisopenapi/webservice/rest/boxoffice/"
            f"searchDailyBoxOfficeList.json?key={kobis_key}&targetDt={target_date}"
        )
        k = requests.get(kobis_url, timeout=10).json()
        box = k["boxOfficeResult"]["dailyBoxOfficeList"]

        for item in box:
            title = item.get("movieNm")
            open_dt = item.get("openDt") or ""
            year = open_dt[:4] if len(open_dt) >= 4 else None
            rank = int(item.get("rank", "999"))

            t = _tmdb_search_one(headers, title, year)
            if t:
                movies.append({
                    "id": t.get("id"),
                    "title": t.get("title") or title,
                    "overview": t.get("overview") or "",
                    "release_date": t.get("release_date"),
                    "vote": t.get("vote_average", 0.0),
                    "poster_url": _img_url(t.get("poster_path")),
                    "rank": rank,
                    "audiCnt": item.get("audiCnt"),
                    "audiAcc": item.get("audiAcc"),
                    "salesAmt": item.get("salesAmt"),
                })
            else:
                movies.append({
                    "id": None,
                    "title": title,
                    "overview": "",
                    "release_date": open_dt or None,
                    "vote": 0.0,
                    "poster_url": "/static/assets/images/default-movie.jpg",
                    "rank": rank,
                    "audiCnt": item.get("audiCnt"),
                    "audiAcc": item.get("audiAcc"),
                    "salesAmt": item.get("salesAmt"),
                })

        # 기본: 랭크 오름차순
        movies.sort(key=lambda x: x.get("rank", 999))

    except Exception as e:
        # 폴백: TMDB 인기 목록
        try:
            params = {"language": "ko-KR", "region": "KR", "page": 1}
            r = requests.get(f"{TMDB_BASE}/movie/popular", headers=headers, params=params, timeout=10)
            r.raise_for_status()
            for m in r.json().get("results", []):
                movies.append({
                    "id": m.get("id"),
                    "title": m.get("title"),
                    "overview": m.get("overview") or "",
                    "release_date": m.get("release_date"),
                    "vote": m.get("vote_average", 0.0),
                    "poster_url": _img_url(m.get("poster_path")),
                    "rank": None,
                })
            tmdb_error = f"KOBIS 호출 실패: {type(e).__name__} - {e}"
        except Exception as e2:
            tmdb_error = f"KOBIS 호출 실패: {type(e).__name__} - {e} | TMDB popular 호출 실패: {type(e2).__name__} - {e2}"

    # 정렬 스위치
    if sort == "recent":
        movies.sort(key=lambda x: x.get("release_date") or "", reverse=True)
    elif sort == "rating":
        movies.sort(key=lambda x: x.get("vote", 0.0), reverse=True)
    else:  # boxoffice
        movies.sort(key=lambda x: x.get("rank") if x.get("rank") is not None else 999)

    return render(request, "movie_list.html", {
        "movies": movies,
        "tmdb_error": tmdb_error or None,
    })


# -----------------------------
# movie_detail: 상세 + 트레일러/감독/출연
# -----------------------------
def movie_detail(request, tmdb_id: int):
    token = getattr(settings, 'TMDB_BEARER_TOKEN', None)
    if not token:
        return render(request, "movie_detail.html", {
            "movie": None,
            "tmdb_error": "TMDB 토큰이 설정되지 않았습니다. settings.TMDB_BEARER_TOKEN를 확인하세요.",
            "comments": [],
            "comment_form": None,
        })

    headers = _auth_headers()
    params = {
        "language": "ko-KR",
        "append_to_response": "videos,credits,release_dates,images",
        "include_image_language": "ko,null,en",
    }

    movie = None
    tmdb_error = None
    try:
        r = requests.get(
            f"{TMDB_BASE}/movie/{tmdb_id}",
            headers=headers,
            params=params,
            timeout=10
        )
        r.raise_for_status()
        m = r.json()

        # 감독
        director = None
        for c in (m.get("credits", {}).get("crew") or []):
            if c.get("job") == "Director":
                director = c.get("name")
                break

        # 출연 상위 5명
        cast = [
            {"name": c.get("name"), "character": c.get("character")}
            for c in (m.get("credits", {}).get("cast") or [])[:5]
        ]

        # 트레일러
        trailer_key = None
        for v in (m.get("videos", {}).get("results") or []):
            if v.get("site") == "YouTube" and v.get("type") in ("Trailer", "Teaser"):
                trailer_key = v.get("key")
                break
        trailer_url = f"https://www.youtube.com/watch?v={trailer_key}" if trailer_key else None

        movie = {
            "id": m.get("id"),
            "title": m.get("title") or m.get("name"),
            "overview": m.get("overview"),
            "genres": [g.get("name") for g in (m.get("genres") or [])],
            "runtime": m.get("runtime"),
            "vote": m.get("vote_average", 0.0),
            "release_date": m.get("release_date"),
            "poster_url": _img_url(m.get("poster_path"), size='w500'),
            "backdrop_url": _img_url(m.get("backdrop_path"), size='w1280'),
            "director": director,
            "cast": cast,
            "trailer_url": trailer_url,
        }
    except Exception as e:
        tmdb_error = f"TMDB 상세 호출 실패: {type(e).__name__} - {e}"

 
    # 이 영화(tmdb_id)에 달린 댓글 전부 가져오기 (최신순)
    comments = Comment.objects.filter(
        movie_tmdb_id=tmdb_id
    ).select_related('user').order_by('-created_at')
    rating_stats = comments.aggregate(
        avg=Avg('rating'),       # rating 평균
        cnt=Count('rating')      # rating이 null이 아닌 개수
    )
    avg_rating = rating_stats['avg'] or 0       # 아무도 안 남겼으면 0
    rating_count = rating_stats['cnt'] or 0     # 별점 단 사람 수

    if request.method == "POST":
        if not request.user.is_authenticated:
            login_url = resolve_url(settings.LOGIN_URL)
            return redirect(f"{login_url}?next={request.path}")

        # ★ 파일까지 함께 받기
        form = CommentForm(request.POST, request.FILES)
        if form.is_valid():
            comment = form.save(commit=False)
            comment.user = request.user
            comment.movie_tmdb_id = tmdb_id
            comment.save()
            messages.success(request, "댓글이 등록되었습니다.")
            return redirect('movie_detail', tmdb_id=tmdb_id)
    else:
        form = CommentForm()
    
    is_favorited = False
    if request.user.is_authenticated:
        is_favorited = Favorite.objects.filter(
            user=request.user,
            movie_tmdb_id=tmdb_id
        ).exists()

    return render(request, "movie_detail.html", {
        "movie": movie,
        "tmdb_error": tmdb_error,
        "comments": comments,
        "comment_form": form,
        "is_favorited": is_favorited,
        "avg_rating": avg_rating,         
        "rating_count": rating_count,     
    })


def favorite_toggle(request, tmdb_id: int):
    # 상태 변경이니까 POST만 허용
    if request.method != "POST":
        return redirect("movie_detail", tmdb_id=tmdb_id)

    if not request.user.is_authenticated:
        return redirect(f"/accounts/login/?next=/movies/{tmdb_id}/")

    fav, created = Favorite.objects.get_or_create(
        user=request.user,
        movie_tmdb_id=tmdb_id,
    )

    if not created:
        # 이미 있으면 -> 해제
        fav.delete()
        messages.info(request, "즐겨찾기에서 제거되었습니다.")
    else:
        messages.success(request, "즐겨찾기에 추가되었습니다.")

    return redirect("movie_detail", tmdb_id=tmdb_id)



def comment_delete(request, comment_id):
    # 로그인 안 했으면 로그인 시키기
    if not request.user.is_authenticated:
        return redirect("/accounts/login/")

    comment = get_object_or_404(Comment, id=comment_id)

    # 본인 댓글만 삭제 가능
    if comment.user != request.user:
        messages.error(request, "본인 댓글만 삭제할 수 있습니다.")
        return redirect(request.META.get("HTTP_REFERER", "/"))

    comment.delete()
    messages.success(request, "댓글이 삭제되었습니다.")

    # 원래 영화 상세 페이지로 되돌아가기
    return redirect(request.META.get("HTTP_REFERER", "/"))

# -----------------------------
# Guess (아키네이터 + 기준 영화 유사도)
# -----------------------------
def guess(request):
    token = getattr(settings, 'TMDB_BEARER_TOKEN', None)
    if not token:
        return render(request, "guess.html", {"error": "TMDB 토큰 미설정"})
    headers = _auth_headers()

    QUESTIONS = [
        # 1단계: 큰 분기
        {"key": "animation",   "text": "이 영화는 애니메이션인가요?"},
        {"key": "country_kr",  "text": "한국 영화인가요?"},
        {"key": "country_jp",  "text": "일본 영화인가요?"},
        {"key": "modern",      "text": "주요 배경이 현대(대략 2000년 이후)인가요?"},

        # 2단계: 장르/테마
        {"key": "genre_action",   "text": "액션/스릴러 요소가 강한 편인가요?"},
        {"key": "genre_romance",  "text": "사랑/연애가 이야기의 중요한 축인가요?"},
        {"key": "genre_sf",       "text": "SF(공상 과학) 요소가 있나요?"},
        {"key": "genre_horror",   "text": "공포/호러 요소가 있나요?"},
        {"key": "genre_comedy",   "text": "코미디 요소가 중요한 편인가요?"},
        {"key": "crime_mystery",  "text": "범죄/추리/느와르 분위기가 강한가요?"},
        {"key": "fantasy",        "text": "비현실적이거나 판타지 요소가 뚜렷한가요?"},

        # 3단계: 분위기
        {"key": "light_mood","text": "전체적으로 밝고 가볍고, 기분 좋아지는 영화인가요?"},
        {"key": "heavy_mood","text": "어둡고 무겁고 진지한 분위기인가요?","parent": "light_mood", "require": "no"},

        # 4단계: 형식/구성
        {"key": "music_heavy",  "text": "노래나 음악 비중이 큰 영화인가요? (뮤지컬/공연 등)"},

        # 5단계: 러닝타임/수위
        {"key": "runtime_long",   "text": "러닝타임이 2시간(120분) 이상인가요?"},
        {"key": "adult_ok","text": "폭력/19금 장면이 있어도 괜찮나요?"},
        {"key": "dislike_gore","text": "피 튀기는 고어한 장면은 피하고 싶나요?","parent": "adult_ok", "require": "yes"},
    ]

    def is_enabled(q, answers):
        parent = q.get("parent")
        require = q.get("require")
        if not parent:
            return True
        val = answers.get(parent)
        if require == "yes":
            return val == "yes"
        if require == "no":
            return val == "no"
        if require == "not_yes":
            return val != "yes"
        return True

    def next_question(answers):
        for q in QUESTIONS:
            if not is_enabled(q, answers):
                continue
            if q["key"] not in answers:
                return q
        return None

    def total_questions(answers):
        return sum(1 for q in QUESTIONS if is_enabled(q, answers))

    state = request.session.get("guess_state") or {"answers": {}}
    answers = state["answers"]

    if request.method == "POST":
        action = request.POST.get("action")
        if action == "reset":
            state = {"answers": {}}
            answers = state["answers"]
        elif action in ("yes", "no", "skip"):
            q = next_question(answers)
            if q:
                answers[q["key"]] = action
        elif action == "back":
            if answers:
                last_key = list(answers.keys())[-1]
                answers.pop(last_key, None)

    request.session["guess_state"] = state

    current_q = next_question(answers)
    question_idx = len(answers)
    total_q = total_questions(answers)
    progress_pct = int(100 * question_idx / total_q) if total_q else 0

    GENRES = {
        "animation": 16,
        "action": 28,
        "crime": 80,
        "horror": 27,
        "thriller": 53,
        "romance": 10749,
        "comedy": 35,
        "family": 10751,
        "music": 10402,
        "mystery": 9648,
        "fantasy": 14,
        "sf": 878,
    }

    params_base = {
        "language": "ko-KR",
        "region": "KR",
        "include_adult": "false",
        "sort_by": "popularity.desc",
        "page": 1,
        "with_origin_country": "KR|US|JP",
    }
    params = dict(params_base)

    with_genres = set()
    without_genres = set()
    origin_countries = set(["KR", "US", "JP"])

    def apply_answer(k, v):
        yes = (v == "yes")
        no = (v == "no")

        if k == "animation":
            if yes:
                with_genres.add(GENRES["animation"])
            elif no:
                without_genres.add(GENRES["animation"])

        elif k == "country_kr":
            if yes:
                origin_countries.clear()
                origin_countries.add("KR")
        elif k == "country_jp":
            if yes:
                origin_countries.clear()
                origin_countries.add("JP")

        elif k == "modern":
            if yes:
                params["primary_release_date.gte"] = "2000-01-01"
                params.pop("primary_release_date.lte", None)
            elif no:
                params["primary_release_date.lte"] = "1999-12-31"
                params.pop("primary_release_date.gte", None)

        elif k == "genre_action":
            if yes:
                with_genres.update({GENRES["action"], GENRES["thriller"]})
            elif no:
                without_genres.add(GENRES["action"])

        elif k == "genre_romance":
            if yes:
                with_genres.add(GENRES["romance"])
            elif no:
                without_genres.add(GENRES["romance"])

        elif k == "genre_sf":
            if yes:
                with_genres.add(GENRES["sf"])

        elif k == "genre_horror":
            if yes:
                with_genres.add(GENRES["horror"])
            elif no:
                without_genres.add(GENRES["horror"])

        elif k == "genre_comedy":
            if yes:
                with_genres.add(GENRES["comedy"])
            elif no:
                without_genres.add(GENRES["comedy"])

        elif k == "crime_mystery":
            if yes:
                with_genres.update({GENRES["crime"], GENRES["mystery"]})

        elif k == "fantasy":
            if yes:
                with_genres.add(GENRES["fantasy"])

        elif k == "light_mood":
            if yes:
                with_genres.update({GENRES["comedy"], GENRES["family"]})
                without_genres.update({GENRES["crime"], GENRES["mystery"], GENRES["thriller"]})  # 무거운 장르는 제외

        elif k == "heavy_mood":
            if yes:
                with_genres.update({GENRES["crime"], GENRES["mystery"], GENRES["thriller"]})
                without_genres.update({GENRES["comedy"], GENRES["family"]})  # 가벼운 장르는 제외

        elif k == "music_heavy":
            if yes:
                with_genres.add(GENRES["music"])

        elif k == "runtime_long":
            if yes:
                params["with_runtime.gte"] = 120
                params.pop("with_runtime.lte", None)
            elif no:
                params["with_runtime.lte"] = 119
                params.pop("with_runtime.gte", None)

        elif k == "adult_ok":
            if no:
                params["certification_country"] = "KR"
                params["certification.lte"] = "15"

        elif k == "dislike_gore":
            if yes:
                without_genres.add(GENRES["horror"])

    for k, v in answers.items():
        if v in ("yes", "no"):
            apply_answer(k, v)

    # 나라 제한 반영
    if origin_countries:
        params["with_origin_country"] = "|".join(sorted(origin_countries))

    # 장르 필터 정리: AND 과도제한 방지 + 충돌 제거
    if with_genres:
        selected = sorted(with_genres)[:2]  # 최대 2개만 AND 조건으로
        with_genres = set(selected)

    # without_genres가 이기는 방향으로 충돌 제거
    with_genres = with_genres - without_genres

    if with_genres:
        params["with_genres"] = ",".join(map(str, sorted(with_genres)))
    if without_genres:
        params["without_genres"] = ",".join(map(str, sorted(without_genres)))

    movies, tmdb_error = [], None

    def fetch_movies(p):
        out = []
        r = requests.get(f"{TMDB_BASE}/discover/movie",
                         headers=headers, params=p, timeout=10)
        r.raise_for_status()
        for m in r.json().get("results", []):
            out.append({
                "id": m.get("id"),
                "title": m.get("title") or m.get("name"),
                "poster_url": _img_url(m.get("poster_path")),
                "vote": m.get("vote_average", 0.0),
                "release_date": m.get("release_date"),
                "popularity": m.get("popularity", 0.0),
            })
        return out

    try:
        movies = fetch_movies(params)

        # 너무 빡세게 걸려서 0개 나오면, 장르/수위 필터 일부 풀고 한 번 더
        if not movies:
            relaxed = dict(params_base)
            if "with_origin_country" in params:
                relaxed["with_origin_country"] = params["with_origin_country"]
            if "primary_release_date.gte" in params:
                relaxed["primary_release_date.gte"] = params["primary_release_date.gte"]
            if "primary_release_date.lte" in params:
                relaxed["primary_release_date.lte"] = params["primary_release_date.lte"]
            if "with_runtime.gte" in params:
                relaxed["with_runtime.gte"] = params["with_runtime.gte"]
            if "with_runtime.lte" in params:
                relaxed["with_runtime.lte"] = params["with_runtime.lte"]
            # 장르/고어/호러 필터는 일단 풀어줌
            movies = fetch_movies(relaxed)

    except Exception as e:
        tmdb_error = f"TMDB 실패: {e}"

    movies.sort(key=lambda x: (x["vote"], x["popularity"]), reverse=True)
    show_results = (len(movies) <= 6) or (current_q is None)

    return render(request, "guess.html", {
        "question_idx": question_idx,
        "total_q": total_q,
        "question": current_q["text"] if current_q else None,
        "movies": movies[:12],
        "tmdb_error": tmdb_error,
        "answers": answers,
        "params_debug": params,
        "show_results": show_results,
        "progress_pct": progress_pct,
    })





# -----------------------------
# 그 외 정적 페이지
# -----------------------------
def details(request):
    return render(request, 'details.html')




@login_required
def streams(request):
    user = request.user

    # 1) 내가 즐겨찾기한 영화들
    favorites = Favorite.objects.filter(user=user).order_by('-created_at')

    favorite_movies = []
    headers = _auth_headers()
    params = {
        "language": "ko-KR",
    }

    for fav in favorites:
        try:
            r = requests.get(
                f"{TMDB_BASE}/movie/{fav.movie_tmdb_id}",
                headers=headers,
                params=params,
                timeout=5
            )
            r.raise_for_status()
            m = r.json()
            favorite_movies.append({
                "id": m.get("id"),
                "title": m.get("title") or m.get("name"),
                "poster_url": _img_url(m.get("poster_path"), size="w300"),
                "release_date": m.get("release_date"),
                "vote": m.get("vote_average", 0.0),
            })
        except Exception:
            # TMDB 에러 나면 그냥 스킵
            continue

    # 2) 내가 쓴 댓글들 (+ 영화제목 붙여주기)
    my_comments_qs = Comment.objects.filter(user=user).order_by("-created_at")

    # 같은 영화에 댓글 여러 개 있을 수 있으니까, TMDB 요청 최소화용
    movie_cache = {}
    my_comments = []
    for c in my_comments_qs:
        tmdb_id = c.movie_tmdb_id
        title = movie_cache.get(tmdb_id)

        if title is None:
            try:
                r = requests.get(
                    f"{TMDB_BASE}/movie/{tmdb_id}",
                    headers=headers,
                    params=params,
                    timeout=5
                )
                r.raise_for_status()
                m = r.json()
                title = m.get("title") or m.get("name") or f"영화 {tmdb_id}"
            except Exception:
                title = f"영화 {tmdb_id}"
            movie_cache[tmdb_id] = title

        my_comments.append({
            "id": c.id,
            "movie_tmdb_id": tmdb_id,
            "movie_title": title,
            "content": c.content,
            "created_at": c.created_at,
        })

    context = {
        "favorite_movies": favorite_movies,
        "my_comments": my_comments,
    }
    return render(request, "streams.html", context)


def search(request):
    query = (request.GET.get("searchKeyword") or "").strip()
    sort = request.GET.get("sort", "relevance")

    tmdb_token = getattr(settings, "TMDB_BEARER_TOKEN", None)
    if not tmdb_token:
        return render(request, "search.html", {
            "movies": [],
            "query": query,
            "tmdb_error": "TMDB 토큰이 설정되지 않았습니다. settings.TMDB_BEARER_TOKEN를 확인하세요.",
            "sort": sort,
        })

    headers = _auth_headers()
    movies = []
    tmdb_error = None

    if query:
        try:
            resp = requests.get(
                f"{TMDB_BASE}/search/movie",
                headers=headers,
                params={
                    "query": query,
                    "language": "ko-KR",
                    "include_adult": "false",
                    "region": "KR",
                    "page": 1,
                },
                timeout=10,
            )
            resp.raise_for_status()
            results = resp.json().get("results", [])

            for m in results:
                tmdb_id = m.get("id")
                tmdb_vote = m.get("vote_average") or 0.0

                user_rating = None
                rating_count = 0
                rating_status = None

                if tmdb_id is not None:
                    stats = Comment.objects.filter(movie_tmdb_id=tmdb_id).aggregate(
                        avg=Avg("rating"),
                        cnt=Count("rating"),
                    )
                    avg_rating = stats["avg"]
                    cnt_rating = stats["cnt"] or 0
                    rating_count = cnt_rating

                    if avg_rating is not None and cnt_rating > 0 and tmdb_vote:
                        user_rating = float(avg_rating)
                        diff = user_rating - tmdb_vote
                        if diff <= -2:
                            rating_status = "over"
                        elif diff >= 2:
                            rating_status = "under"
                        else:
                            rating_status = "fair"

                movies.append({
                    "tmdb_id": tmdb_id,
                    "title": m.get("title") or m.get("name"),
                    "overview": m.get("overview") or "",
                    "release_date": m.get("release_date"),
                    "poster_url": _img_url(m.get("poster_path")),
                    "tmdb_vote": tmdb_vote,
                    "user_rating": user_rating,
                    "rating_count": rating_count,
                    "rating_status": rating_status,
                })

        except Exception as e:
            tmdb_error = f"TMDB 검색 호출 실패: {type(e).__name__} - {e}"

    if movies:
        if sort == "recent":
            movies.sort(key=lambda m: m.get("release_date") or "", reverse=True)
        elif sort == "rating":
            movies.sort(key=lambda m: m.get("tmdb_vote") or 0.0, reverse=True)

    return render(request, "search.html", {
        "movies": movies,
        "query": query,
        "tmdb_error": tmdb_error,
        "sort": sort,
    })

