from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAdminUser
from rest_framework.exceptions import NotFound
from drf_yasg.utils import swagger_auto_schema
from .models import Job
from .serializers import JobSerializer,JobListSerializer
from .pagination import JobPagination

# Job List View
class JobListView(APIView):
    permission_classes = [AllowAny]

    @swagger_auto_schema(
        responses={200: JobListSerializer(many=True)},
        operation_description="""
         Retrieve a paginated list of available jobs.

        This endpoint returns job listings with limited fields required
        for the job listing page.
        """
    )
    def get(self, request):
        jobs = Job.objects.only(
            "job_role",
            "total_vacancies",
            "experience",
            "location",
            "package"
        ).order_by("-id")

        paginator = JobPagination()
        paginated_jobs = paginator.paginate_queryset(jobs, request)
        serializer = JobListSerializer(paginated_jobs, many=True)
        return paginator.get_paginated_response(serializer.data)

#Job create view
class JobCreateView(APIView):
    permission_classes = [AllowAny]
    # Create Job
    @swagger_auto_schema(
        request_body=JobSerializer,
        responses={
            201: JobSerializer,
            400: "Validation Error"
        },
        operation_description="""
        Create a new job posting.

        Only administrators are allowed to create job postings.
        """
    )
    def post(self, request):
        serializer = JobSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_201_CREATED)

#update view
class JobUpdateView(APIView):
    permission_classes = [AllowAny]

    def get_object(self, pk):
        try:
            return Job.objects.get(pk=pk)
        except Job.DoesNotExist:
            raise NotFound("Job not found")

    # Full Update 
    @swagger_auto_schema(
        request_body=JobSerializer,
        responses={
            200: JobSerializer,
            404: "Job not found"
        },
        operation_description="""
        Fully update an existing job.

        This replaces the entire job object.
        """
    )
    def put(self, request, pk):
        job = self.get_object(pk)
        serializer = JobSerializer(job, data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)


    # Partial Update 
    @swagger_auto_schema(
        request_body=JobSerializer,
        responses={
            200: JobSerializer,
            404: "Job not found"
        },
        operation_description="""
        Partially update a job.

        Only specific fields can be updated.
        """
    )
    def patch(self, request, pk):
        job = self.get_object(pk)
        serializer = JobSerializer(job, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(serializer.data)
       
    # Delete Job
    @swagger_auto_schema(
        responses={
            204: "Job deleted successfully",
            404: "Job not found"
        },
        operation_description="""
        Delete a job posting.

        Once deleted, the job cannot be recovered.
        """
    )
    def delete(self, request, pk):
        job = self.get_object(pk)
        job.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)