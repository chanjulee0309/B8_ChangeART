""" 게시글&댓글&메인페이지

    * user가 아닌 모든 view의 처리 

Todo:

    * HomeView 만들기
    * 이미지 변환 view 만들기 
    * 다중 이미지 처리 view 만들기

"""
from rest_framework import status, permissions
from rest_framework.views import APIView
from rest_framework.generics import get_object_or_404
from rest_framework.response import Response
from rest_framework_simplejwt.authentication import JWTAuthentication
from .models import Article, Comment, Images
from django.db.models import Count, F
from .serializers import (
    ArticleCreateSerializer,
    ArticleDetailSerializer,
    CommentSerializer,
)
import ast


class HomeView(APIView):
    permission_classes = [permissions.AllowAny]

    def get(self, request):
        """홈 화면에서 게시글 목록을 반환"""
        order_by = request.query_params.get("order_by")

        if order_by == "likes":
            articles = Article.objects.all().order_by("-likes", "-created_at")
        elif order_by == "latest":
            articles = Article.objects.all().order_by("-created_at")
        elif order_by == "comments":
            articles = Article.objects.annotate(
                comment_count=Count("comments")
            ).order_by("-comment_count", "-created_at")
        else:
            articles = Article.objects.all().order_by("-created_at")

        serializer = ArticleDetailSerializer(articles, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class ArticleView(APIView):
    permission_classes = [permissions.IsAuthenticatedOrReadOnly]
    authentication_classes = [JWTAuthentication]

    def get(self, request, article_id):
        """상세 게시글 보기"""
        article = get_object_or_404(Article, id=article_id)
        serializer = ArticleDetailSerializer(article)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request):
        """게시글 작성"""
        serializer = ArticleCreateSerializer(
            data=request.data, context={"request": request}
        )

        if serializer.is_valid():
            serializer.save(user=request.user)
            return Response({"message": "게시글을 등록했습니다."}, status=status.HTTP_200_OK)
        else:
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def put(self, request, article_id):
        """게시글 수정"""
        article = get_object_or_404(Article, id=article_id)
        delete_images = request.data.get("delete_images", [])
        delete_images = ast.literal_eval(delete_images)
        # 이미지 인덱스(id)가 게시글에 종속되었는지 체크해줘야 함!

        if request.user == article.user:
            serializer = ArticleCreateSerializer(
                article, data=request.data, context={"request": request}
            )
            if serializer.is_valid():
                serializer.save(user=request.user)

                # 이미지 선택해서 삭제
                if delete_images:
                    Images.objects.filter(
                        id__in=delete_images, article=article
                    ).delete()

                return Response({"message": "게시글이 수정되었습니다."}, status=status.HTTP_200_OK)
            else:
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        else:
            return Response("본인만 수정할 수 있습니다.", status=status.HTTP_403_FORBIDDEN)

    def delete(self, request, article_id):
        """게시글 삭제"""
        article = get_object_or_404(Article, id=article_id)

        if request.user == article.user:
            article.delete()
            return Response(
                {"message": "게시글이 삭제되었습니다."}, status=status.HTTP_204_NO_CONTENT
            )
        else:
            return Response("작성자만 삭제할 수 있습니다.", status=status.HTTP_403_FORBIDDEN)


class ArticleLikeView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    authentication_classes = [JWTAuthentication]

    def post(self, request, article_id):
        article = get_object_or_404(Article, id=article_id)
        """좋아요"""
        if request.user in article.like.all():
            article.like.remove(request.user)
            return Response({"message": "좋아요를 취소했습니다."}, status=status.HTTP_200_OK)
        else:
            article.like.add(request.user)
            return Response({"message": "좋아요를 했습니다."}, status=status.HTTP_200_OK)


class CommentView(APIView):
    """댓글 CRUD를 위한 뷰"""

    permission_classes = [permissions.IsAuthenticated]

    def post(self, request, article_id):
        """댓글 작성

        댓글의 content 필드를 작성합니다.

        Args:
            article_id : 보고있는 게시글의 PK

        Returns:
            HTTP_200_OK : 댓글 작성 성공

            HTTP_400_BAD_REQUEST : validation 실패

            HTTP_404_NOT_FOUND : 게시글 연결 실패
        """
        serializer = CommentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(
            user=request.user, article=get_object_or_404(Article, id=article_id)
        )
        return Response(serializer.data, status=status.HTTP_200_OK)

    def put(self, request, comment_id):
        """댓글 수정

        댓글의 content 필드를 수정합니다.

        Args:
            comment_id : 수정, 삭제를 하려는 댓글의 PK

        Returns:
            HTTP_200_OK : 댓글 수정 성공

            HTTP_400_BAD_REQUEST : validation 실패

            HTTP_404_NOT_FOUND : 댓글 연결 실패

            HTTP_403_FORBIDDEN : 댓글의 작성자가 아님
        """
        comment = get_object_or_404(Comment, pk=comment_id)
        if request.user == comment.user:
            serializer = CommentSerializer(comment, data=request.data)
            serializer.is_valid(raise_exception=True)
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        else:
            return Response({"message": "put 요청 실패"}, status=status.HTTP_403_FORBIDDEN)

    def delete(self, request, comment_id):
        """댓글 삭제

        Args:
            comment_id : 수정, 삭제를 하려는 댓글의 PK

        Returns:
            HTTP_200_OK : 댓글 삭제 성공

            HTTP_400_BAD_REQUEST : validation 실패

            HTTP_404_NOT_FOUND : 댓글 연결 실패

            HTTP_403_FORBIDDEN : 댓글의 작성자가 아님
        """
        comment = get_object_or_404(Comment, pk=comment_id)
        if request.user == comment.user:
            comment.delete()
            return Response({"message": "댓글 삭제"}, status=status.HTTP_200_OK)
        else:
            return Response(
                {"message": "delete 요청 실패"}, status=status.HTTP_403_FORBIDDEN
            )
