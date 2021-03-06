# Create your views here.
import json
from datetime import datetime

from django.http import JsonResponse

from blockchain.models import Delegation, Exchange, BlockChain
from dns_project.utils import log, ca_check, view_ca_cert, request_cert_from_ca


def request_cert(request):
    model = BlockChain.load()
    certs = request_cert_from_ca('blockchain')
    model.public_key = certs['public_key']
    model.private_key = certs['private_key']
    model.certificate = certs['certificate']
    model.save()
    return JsonResponse(certs)


def view_cert(request):
    name = json.loads(request.body).get('name', None)
    data = view_ca_cert(name, 'blockchain')
    url = 'https://127.0.0.1:8090/ca/get_cert'
    return JsonResponse(data=data)


@ca_check
def delegate(request):
    body = json.loads(request.body)
    user = body['pkm']
    delegated_to = body['pkd']
    policy = body['policy']
    log(
        f'blockchain delegate called with user, delegated_to, policy, nonce: {user}, {delegated_to}, {policy},'
        f' {body["nonce"]}')
    last_delegation = Delegation.objects.last()
    if last_delegation and last_delegation.nonce == body['nonce']:
        return JsonResponse({
            'status': 'duplicate'
        }, status=400)
    # ---> connect to blockchain nodes
    Delegation.objects.create(user=user, delegated_to=delegated_to, amount=policy['amount'],
                              current_value=policy['amount'], count=policy['count'],
                              time=policy['time'], nonce=body['nonce'])
    return JsonResponse({
        'status': 'ok',
        'nonce': body['nonce']
    })


@ca_check
def exchange(request):
    body = json.loads(request.body)
    sender = body['sender']
    receiver = body['receiver']
    value = body['value']
    log(
        f'blockchain exchange called with sender, receiver, value, nonce: {sender}, {receiver}, {value},'
        f' {body["nonce"]}')
    last_exchange = Exchange.objects.last()
    if last_exchange and last_exchange.nonce == body['nonce']:
        return JsonResponse({
            'status': 'duplicate'
        }, status=400)
    delegation = Delegation.objects.filter(delegated_to=sender, current_value__gte=value, count__gt=0,
                                           time__gte=datetime.now()).first()
    if not delegation:
        return JsonResponse({
            'status': 'no-delegation'
        }, status=404)
    Exchange.objects.create(sender=sender, receiver=receiver, amount=value, delegation=delegation, nonce=body['nonce'])
    delegation.amount -= value
    delegation.count -= 1
    delegation.save()
    return JsonResponse({
        'status': 'ok',
        'nonce': body['nonce']
    })
