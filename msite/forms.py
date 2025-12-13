from django import forms
from .models import Comment  

class CommentForm(forms.ModelForm):  # 댓글 작성에 사용할 ModelForm
    class Meta:
        model = Comment  
    
        fields = ['content', 'image', 'rating']

        widgets = {
          
            "content": forms.Textarea(
                attrs={
                    "rows": 3,
                    "placeholder": "내용을 입력하세요",
                  
                }
            ),
            "rating": forms.HiddenInput(),

       
        }

     
        labels = {
            'content': '',              
            'image': '이미지 첨부(선택)',  
        }
