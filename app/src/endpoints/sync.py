import itertools
import json

from json import JSONDecodeError

from fastapi import APIRouter, Request, Depends, HTTPException
from fastapi_restful.cbv import cbv
from datetime import datetime

from app.dependencies import get_settings, get_network
from app.utils.config import Settings
from app.utils.network import Network
from operator import itemgetter

from time import time

router = APIRouter(
    # prefix="/sync",
    tags=["/sync"]
)


@cbv(router)
class Sync:
    def __init__(self, settings: Settings = Depends(get_settings), network: Network = Depends(get_network)):
        self.settings = settings
        self.network = network

    @staticmethod
    def __set_audit(
            data: dict,
            audit_key: str | None,
            s_data: dict = None
    ) -> None:
        if audit_key is not None:
            if s_data is None:
                data[audit_key] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            else:
                data[audit_key] = s_data[audit_key]

    @staticmethod
    def __decode_json(value) -> list[dict]:
        try:
            return json.loads(value)
            # print("LOCAL DATA:", local_data)
        except (JSONDecodeError, TypeError) as e:
            print(f"Error: {e}")
            print(value)
            raise HTTPException(
                detail="Error: Error while trying to decode malformed JSON.",
                status_code=400
            )

    def __delete_on_server(
            self,
            server_data: list[dict],
            s_data_index: int,
            s_data: dict | None
    ) -> None:
        if s_data is not None:
            if self.settings.sorting_key is not None:
                s_data[self.settings.sorting_key] = None

            if self.settings.deleted_at_key is not None:
                s_data[self.settings.deleted_at_key] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            else:
                del server_data[s_data_index]

    def __add_on_server(
            self,
            s_data: dict | None,
            l_data: dict,
            server_data: list[dict]
    ) -> None:
        if s_data is None:
            self.__set_audit(l_data, self.settings.created_at_key)
            self.__set_audit(l_data, self.settings.updated_at_key)
            server_data.append(l_data)

            # Look for children to delete the three fields needed to sync (and to calculate hash in future)
            self.__loop_data_attrs(l_data, s_data)
        else:
            if s_data.get(self.settings.deleted_at_key) is not None:
                s_data[self.settings.deleted_at_key] = None

                if self.settings.sorting_key is not None:
                    s_data[self.settings.sorting_key] = l_data[self.settings.sorting_key]

                self.__set_audit(s_data, self.settings.updated_at_key)
                # print("to add on server, but it was deleted -> recovered from trash")
            else:
                # print("same data has been added by other device, and you didn't refresh")

                raise HTTPException(
                    detail="Error: You are trying to insert a data with "
                           f"unique key: {l_data[self.settings.unique_key]} "
                           "but it conflicts because it is already present on the server. "
                           "Try syncing before pushing your changes. ",
                    status_code=409
                )

    def __edit_on_server(
            self,
            l_data: dict,
            s_data: dict
    ) -> None:
        self.__set_audit(l_data, self.settings.updated_at_key)
        self.__set_audit(l_data, self.settings.created_at_key, s_data)

        self.__loop_data_attrs(l_data, s_data, False)

    def __sorting_value_validation_and_correction(
            self,
            sync_data_for_local: list[dict],
            server_data_by_unique: dict
    ) -> None:
        # check if list is not empty and if (for example) the first item has the sorting key -> this tells me that
        # the list has to be sorted by key
        if len(sync_data_for_local) > 0 and sync_data_for_local[0].get(self.settings.sorting_key) is not None:
            sync_data_for_local.sort(key=itemgetter(self.settings.sorting_key))

            if sync_data_for_local[0][self.settings.sorting_key] != 0:
                sync_data_for_local[0][self.settings.sorting_key] = 0

                s_data = server_data_by_unique[sync_data_for_local[0][self.settings.unique_key]]

                if s_data is not None:
                    s_data[self.settings.sorting_key] = 0

            for i in range(len(sync_data_for_local) - 1):
                if (sync_data_for_local[i + 1][self.settings.sorting_key] -
                        sync_data_for_local[i][self.settings.sorting_key] != 1):
                    sync_data_for_local[i + 1][self.settings.sorting_key] = \
                        sync_data_for_local[i][self.settings.sorting_key] + 1

                    s_data = server_data_by_unique[sync_data_for_local[i + 1][self.settings.unique_key]]

                    if s_data is not None:
                        s_data[self.settings.sorting_key] = \
                            sync_data_for_local[i + 1][self.settings.sorting_key]

    def __loop_data_attrs(
            self,
            l_data: dict,
            s_data: dict | None,
            edit_on_local: bool | None = None
    ) -> None:
        for key, value in l_data.items():
            if (key == self.settings.primary_key or
                    key == self.settings.unique_key or
                    key == self.settings.is_new_key or
                    key == self.settings.updated_key or
                    key == self.settings.deleted_key):
                continue

            if type(value) is dict:
                l_data[key], _ = self.__compare([value], s_data[key] if s_data is not None else [])
            elif type(value) is list:
                l_data[key], _ = self.__compare(value, s_data[key] if s_data is not None else [])
            elif s_data is not None and value != s_data[key]:
                if edit_on_local:
                    l_data[key] = s_data[key]
                else:
                    s_data[key] = l_data[key]

    def __loop_local_data(
            self,
            local_data: list[dict],
            server_data: list[dict],
            sync_data_for_local: list[dict],
            to_add_to_server_data: list[dict],
            server_data_by_unique: dict
    ) -> None:
        for l_data in local_data:
            s_data_index = next(
                (i for i, x in enumerate(server_data) if
                 x[self.settings.unique_key] == l_data[self.settings.unique_key]),
                None
            )
            s_data = None if s_data_index is None else server_data[s_data_index]
            server_data_by_unique[l_data[self.settings.unique_key]] = s_data

            to_add_in_local_response = True

            if l_data[self.settings.deleted_key]:
                to_add_in_local_response = False
                self.__delete_on_server(server_data, s_data_index, s_data)

                # print("to delete on server")
            elif l_data[self.settings.is_new_key]:
                self.__add_on_server(s_data, l_data, to_add_to_server_data)
                # print("to add on server")
            elif s_data is None or s_data.get(self.settings.deleted_at_key) is not None:
                to_add_in_local_response = False
                # print("to delete on local")
            elif l_data[self.settings.updated_key] and s_data.get(self.settings.deleted_at_key) is None:
                self.__edit_on_server(l_data, s_data)
                # print("to edit on server")
            elif s_data.get(self.settings.deleted_at_key) is None:
                self.__loop_data_attrs(l_data, s_data, True)
                # print("to edit on local")

            if to_add_in_local_response:
                del l_data[self.settings.is_new_key]
                del l_data[self.settings.updated_key]
                del l_data[self.settings.deleted_key]

                sync_data_for_local.append(l_data)

    def __loop_server_data(
            self,
            server_data: list[dict],
            sync_data_for_local: list[dict],
            server_data_by_unique: dict
    ) -> None:
        for s_data in server_data:
            if (s_data.get(self.settings.deleted_at_key) is None and
                    s_data[self.settings.unique_key] not in server_data_by_unique):
                sync_data_for_local.append(s_data)
                server_data_by_unique[s_data[self.settings.unique_key]] = s_data
                # print("to add data on local")

    def __compare(
            self,
            local_data: list[dict],
            server_data: list[dict]
    ) -> tuple[list[dict], list[dict]]:
        sync_data_for_local: list[dict] = []
        to_add_to_server_data: list[dict] = []
        server_data_by_unique: dict = {}  # {unique_key: server_data}

        self.__loop_local_data(local_data, server_data, sync_data_for_local, to_add_to_server_data,
                               server_data_by_unique)

        self.__loop_server_data(server_data, sync_data_for_local, server_data_by_unique)

        # concatenate the two lists
        server_data = list(itertools.chain(server_data, to_add_to_server_data))

        self.__sorting_value_validation_and_correction(sync_data_for_local, server_data_by_unique)

        return sync_data_for_local, server_data

    @router.post("/sync")
    async def sync(self, request: Request):
        a = z = time()

        local_data = self.__decode_json(await request.json())

        b = time() - a

        # print("--------------------- PULL FROM SERVER ---------------------------")
        server_data = self.__decode_json(await self.network.send_get(request, self.settings.pull_url))

        c = time()

        sync_data_local, sync_data_server = self.__compare(local_data, server_data)

        print("\n\nsync_data_for_local:", sync_data_local)
        print("sync_data_for_server:", sync_data_server)

        d = time() - c

        print("\n\n\nJSON DECODE PERFORMANCE TIME: ", b)
        print("\nCOMPARING PERFORMANCE TIME: ", d)
        print("\nTOTAL PERFORMANCE TIME WITHOUT EXTERNAL REQUEST: ", b + d)

        # print("--------------------- PUSH TO SERVER ---------------------------")
        await self.network.send_post(request, self.settings.push_url, json.dumps(sync_data_server))

        print("\nTOTAL PERFORMANCE TIME WITH EXTERNAL REQUEST: ", time() - z)

        return sync_data_local
