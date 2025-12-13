from django.db import models
from django.contrib.auth.models import User

class Comment(models.Model):
    # TMDB 영화 ID를 저장한다고 가정 (movie_detail(movie_id) 형태일 때)
    movie_tmdb_id = models.IntegerField(db_index=True)
    
    # 댓글 작성자
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    # 댓글 내용
    content = models.TextField()

    image = models.ImageField(
        upload_to="comments/",   # S3 버킷 안에서 폴더 경로 (예: comments/파일이름.jpg)
        null=True,               # 이미지 없이도 댓글 가능
        blank=True
    )
    RATING_CHOICES = [(i, str(i)) for i in range(1, 11)]
    rating = models.PositiveSmallIntegerField(
        choices=RATING_CHOICES,   # 1~5 중 하나
        null=True,                # 안 줄 수도 있게
        blank=True
    )

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user} - {self.movie} ({self.rating or "no rating"})'
    # 생성 / 수정 시간
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.user.username} - {self.movie_tmdb_id}'
# Create your models here.
class Favorite(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    movie_tmdb_id = models.IntegerField(db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'movie_tmdb_id')  # 하나의 영화는 한 번만 즐겨찾기

    def __str__(self):
        return f"{self.user.username} - {self.movie_tmdb_id}"
    
