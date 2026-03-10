from rest_framework.pagination import PageNumberPagination


class TenUserPagination(PageNumberPagination):
    page_size = 10