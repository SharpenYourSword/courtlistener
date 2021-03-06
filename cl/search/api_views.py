from rest_framework import status, pagination, viewsets, permissions, response

from cl.api.routers import get_api_read_db
from cl.api.utils import LoggingMixin, RECAPUsersReadOnly, CacheListMixin
from cl.search import api_utils
from cl.search.api_serializers import (
    DocketSerializer, CourtSerializer, OpinionClusterSerializer,
    OpinionSerializer, SearchResultSerializer,
    OpinionsCitedSerializer, DocketEntrySerializer, RECAPDocumentSerializer,
    TagSerializer, OriginalCourtInformationSerializer,
)
from cl.search.filters import (
    DocketFilter, CourtFilter, OpinionClusterFilter, OpinionFilter,
    OpinionsCitedFilter, DocketEntryFilter, RECAPDocumentFilter,
)
from cl.search.forms import SearchForm
from cl.search.models import (
    Court, Docket, DocketEntry, Opinion, OpinionCluster, OpinionsCited,
    OriginatingCourtInformation, RECAPDocument, Tag,
)


class OriginatingCourtInformationViewSet(viewsets.ModelViewSet):
    serializer_class = OriginalCourtInformationSerializer

    def get_queryset(self):
        return OriginatingCourtInformation.objects.using(
            get_api_read_db()).all()


class DocketViewSet(LoggingMixin, viewsets.ModelViewSet):
    serializer_class = DocketSerializer
    filter_class = DocketFilter
    ordering_fields = (
        'date_created', 'date_modified', 'date_argued', 'date_reargued',
        'date_reargument_denied', 'date_blocked', 'date_cert_granted',
        'date_cert_denied', 'date_filed', 'date_terminated',
        'date_last_filing',
    )

    def get_queryset(self):
        return Docket.objects.using(get_api_read_db()).select_related(
            'court',
            'assigned_to',
            'referred_to',
            'originating_court_information',
            'idb_data',
        ).prefetch_related(
            'panel',
            'clusters',
            'audio_files',
            'tags',
        )


class DocketEntryViewSet(LoggingMixin, viewsets.ModelViewSet):
    permission_classes = (RECAPUsersReadOnly,)
    serializer_class = DocketEntrySerializer
    filter_class = DocketEntryFilter
    ordering_fields = ('date_created', 'date_modified', 'date_filed')

    def get_queryset(self):
        return DocketEntry.objects.using(get_api_read_db()).select_related(
            'docket',  # For links back to dockets
        ).prefetch_related(
            'recap_documents',        # Sub items
            'recap_documents__tags',  # Sub-sub items
            'tags',                   # Tags on docket entries
        ).order_by()


class RECAPDocumentViewSet(LoggingMixin, CacheListMixin,
                           viewsets.ModelViewSet):
    permission_classes = (RECAPUsersReadOnly,)
    serializer_class = RECAPDocumentSerializer
    filter_class = RECAPDocumentFilter
    ordering_fields = ('date_created', 'date_modified', 'date_upload')

    def get_queryset(self):
        return RECAPDocument.objects.using(get_api_read_db()).select_related(
            'docket_entry',
            'docket_entry__docket',
        ).prefetch_related(
            'tags',
        ).order_by()


class CourtViewSet(LoggingMixin, viewsets.ModelViewSet):
    serializer_class = CourtSerializer
    filter_class = CourtFilter
    ordering_fields = (
        'date_modified', 'position', 'start_date', 'end_date',
    )

    def get_queryset(self):
        return Court.objects.using(get_api_read_db()).exclude(
            jurisdiction=Court.TESTING_COURT)


class OpinionClusterViewSet(LoggingMixin, viewsets.ModelViewSet):
    serializer_class = OpinionClusterSerializer
    filter_class = OpinionClusterFilter
    ordering_fields = (
        'date_created', 'date_modified', 'date_filed', 'citation_count',
        'date_blocked',
    )

    def get_queryset(self):
        return OpinionCluster.objects.using(
            get_api_read_db(),
        ).prefetch_related(
            'sub_opinions',
            'panel',
            'non_participating_judges',
            'citations',
        )


class OpinionViewSet(LoggingMixin, viewsets.ModelViewSet):
    serializer_class = OpinionSerializer
    filter_class = OpinionFilter
    ordering_fields = (
        'id', 'date_created', 'date_modified',
    )

    def get_queryset(self):
        return Opinion.objects.using(get_api_read_db()).select_related(
            'cluster',
            'author',
        ).prefetch_related(
            'opinions_cited',
            'joined_by',
        )


class OpinionsCitedViewSet(LoggingMixin, viewsets.ModelViewSet):
    serializer_class = OpinionsCitedSerializer
    filter_class = OpinionsCitedFilter

    def get_queryset(self):
        return OpinionsCited.objects.using(get_api_read_db()).all()


class TagViewSet(LoggingMixin, viewsets.ModelViewSet):
    permission_classes = (RECAPUsersReadOnly,)
    serializer_class = TagSerializer

    def get_queryset(self):
        return Tag.objects.using(get_api_read_db()).all()


class SearchViewSet(LoggingMixin, viewsets.ViewSet):
    # Default permissions use Django permissions, so here we AllowAny,
    # but folks will need to log in to get past the thresholds.
    permission_classes = (permissions.AllowAny,)

    def list(self, request, *args, **kwargs):
        search_form = SearchForm(request.GET)
        if search_form.is_valid():
            cd = search_form.cleaned_data
            if cd['q'] == '':
                cd['q'] = '*'  # Get everything

            paginator = pagination.PageNumberPagination()
            sl = api_utils.get_object_list(request, cd=cd, paginator=paginator)

            result_page = paginator.paginate_queryset(sl, request)
            serializer = SearchResultSerializer(
                result_page,
                many=True,
                context={'schema': sl.conn.schema}
            )
            return paginator.get_paginated_response(serializer.data)

        # Invalid search.
        return response.Response(
            search_form.errors,
            status=status.HTTP_400_BAD_REQUEST
        )
