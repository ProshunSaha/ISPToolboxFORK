from django.views import View
from django.shortcuts import render
from django.http import JsonResponse
from django.core.exceptions import PermissionDenied
from dataUpdate.models import Source
from django.conf import settings
from django.core.cache import cache
from dataUpdate.scripts.load_asn_elasticsearch import queryASNElasticCache


class CountrySourceUpdatedView(View):
    def get(self, request):
        """
            Returns a list of json objects representing last updated dates for sources.
        """
        country = request.GET.get("country", "")
        if not country:
            return JsonResponse({"error": "Country not found"})
        sources = Source.objects.filter(source_country=country)
        resp = list(
            map(
                lambda s: {
                    "id": s.source_id,
                    "month": s.last_updated.strftime("%b"),
                    "year": str(s.last_updated.year),
                },
                sources,
            )
        )
        return JsonResponse(resp, safe=False)


class ASNElasticSearchView(View):
    def validate_auth_header(self, request):
        expected_token = f'Bearer {settings.SOCIAL_AUTH_FACEBOOK_KEY}|{settings.ASN_CURL_SECRET}'
        return request.headers.get('Authorization', None) == expected_token

    def get(self, request):
        if request.user.is_superuser or self.validate_auth_header(request):
            query = request.GET.get('query', None)
            context = {'error': None, 'query': query, 'results': None, 'cached': 'True'}
            if query is not None:
                try:
                    key = 'asn-es-' + query
                    result = cache.get(key)
                    if result is None:
                        result = queryASNElasticCache(query)
                        context.update({'cached': 'False'})
                        cache.set(key, result, 60 * 60 * 24)  # cache result for 1 day
                    context.update({
                        'results': result
                    })
                except Exception:
                    context.update({
                        'error': 'An Error Occured'
                    })
            if request.GET.get('format', None) == 'json':
                return JsonResponse(context)
            return render(request, 'asn/asn-check.html', context)
        else:
            raise PermissionDenied
