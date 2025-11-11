from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from utils.constants import CONSTANTS


def send_to_socket(data, keys=None) -> None:
    """
    Sends data to the specified channel.
    Out of the box, it sends data outside the consumers.

    :param data: Data to send
    :param keys: Channel name
    :return: None
    """
    if keys:
        if not isinstance(keys, (list, tuple)):
            keys = [keys]

        sent_keys = set()
        for key in keys:
            if key not in sent_keys:
                sent_keys.add(key)
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    key,
                    {
                        'type': 'send.socket',
                        'message': data
                    }
                )


def send_to_user_socket(message, *user_ids):
    """
    Send a message to specific users via WebSocket.

    :param message: The message to be sent.
    :param user_ids: List of user IDs to receive the message.
    """

    socket_keys = ["user_%s" % str(user_id) for user_id in user_ids]
    send_to_socket(message, keys=socket_keys)


def send_to_group_chat_socket(message, group_chat_id):
    """
    Send a message to a group chat via WebSocket.

    :param message: The message to be sent.
    :param group_chat_id: The ID of the group chat.
    """

    socket_key = "%s_%s" % (CONSTANTS.CHAT.TYPES.GROUP, str(group_chat_id))
    send_to_socket(message, keys=socket_key)


def send_to_private_chat_socket(message, private_chat_id):
    """
    Send a message to a private chat via WebSocket.

    :param message: The message to be sent.
    :param private_chat_id: The ID of the private chat.
    """

    socket_key = "%s_%s" % (CONSTANTS.CHAT.TYPES.PRIVATE, str(private_chat_id))
    send_to_socket(message, keys=socket_key)
