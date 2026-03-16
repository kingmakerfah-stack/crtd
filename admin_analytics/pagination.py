from rest_framework.pagination import PageNumberPagination


class TestimonialPagination(PageNumberPagination):

    page_size = 10