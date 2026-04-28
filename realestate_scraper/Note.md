



atus=failed listings=0 strategy=none reason=site_not_reachable in 100.1s
04:00:34 INFO    scraper.pipeline | done tit-immobilier.com status=failed listings=0 strategy=none reason=site_not_reachable in 100.0s
04:00:34 INFO    scraper.pipeline | done groupimmo.pro status=failed listings=0 strategy=none reason=site_not_reachable in 100.1s
04:00:34 INFO    scraper.pipeline | done imbs-immo.com status=failed listings=0 strategy=none reason=site_not_reachable in 100.1s
04:00:34 INFO    scraper.pipeline | done vancia-immobilier.fr status=failed listings=0 strategy=none reason=site_not_reachable in 100.2s


04:03:45 INFO    scraper.pipeline | done piriac-immobilier.fr status=failed listings=0 strategy=none reason=site_not_reachable in 95.2s
04:03:45 INFO    scraper.pipeline | done agencecoullaud.fr status=failed listings=0 strategy=none reason=site_not_reachable in 387.6s
04:03:45 INFO    scraper.pipeline | done 2m-immo.com status=failed listings=0 strategy=none reason=site_not_reachable in 387.6s



^C^C^CException ignored in: <coroutine object run_pipeline at 0x76703c13de70>
Traceback (most recent call last):
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/scraper/pipeline.py", line 497, in run_pipeline
    await pipeline.run(pending)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/scraper/pipeline.py", line 87, in run
    async with open_fetcher(self._settings) as fetcher:
  File "/usr/lib/python3.12/contextlib.py", line 231, in __aexit__
    await self.gen.athrow(value)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/scraper/http_client.py", line 297, in open_fetcher
    async with httpx.AsyncClient(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/httpx/_client.py", line 2016, in __aexit__
    await self._transport.__aexit__(exc_type, exc_value, traceback)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/httpx/_transports/default.py", line 372, in __aexit__
    await self._pool.__aexit__(exc_type, exc_value, traceback)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/httpcore/_async/connection_pool.py", line 364, in __aexit__
    await self.aclose()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/httpcore/_async/connection_pool.py", line 353, in aclose
    await self._close_connections(closing_connections)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/httpcore/_async/connection_pool.py", line 343, in _close_connections
    with AsyncShieldCancellation():
         ^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/httpcore/_synchronization.py", line 208, in __init__
    self._anyio_shield = anyio.CancelScope(shield=True)
                         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/anyio/_core/_tasks.py", line 33, in __new__
    return get_async_backend().create_cancel_scope(shield=shield, deadline=deadline)
           ^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/anyio/_core/_eventloop.py", line 189, in get_async_backend
    raise NoEventLoopError(
anyio.NoEventLoopError: Not currently running on any asynchronous event loop. Available async backends: asyncio, trio
04:09:53 ERROR   asyncio | Task was destroyed but it is pending!
task: <Task cancelling name='Task-1' coro=<run_pipeline() done, defined at /home/softverse/FR-realestate-scraping/realestate_scraper/scraper/pipeline.py:448> wait_for=<Future pending cb=[Task.task_wakeup()]> cb=[gather.<locals>._done_callback() at /usr/lib/python3.12/asyncio/tasks.py:767, ProtocolCallback.__init__.<locals>.cb() at /home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py:230]>
Exception ignored in: <function BaseSubprocessTransport.__del__ at 0x76703dc56160>
Traceback (most recent call last):
  File "/usr/lib/python3.12/asyncio/base_subprocess.py", line 126, in __del__
    self.close()
  File "/usr/lib/python3.12/asyncio/base_subprocess.py", line 104, in close
    proto.pipe.close()
  File "/usr/lib/python3.12/asyncio/unix_events.py", line 767, in close
    self.write_eof()
  File "/usr/lib/python3.12/asyncio/unix_events.py", line 753, in write_eof
    self._loop.call_soon(self._call_connection_lost, None)
  File "/usr/lib/python3.12/asyncio/base_events.py", line 795, in call_soon
    self._check_closed()
  File "/usr/lib/python3.12/asyncio/base_events.py", line 541, in _check_closed
    raise RuntimeError('Event loop is closed')
RuntimeError: Event loop is closed
04:09:53 ERROR   asyncio | Task was destroyed but it is pending!
task: <Task cancelling name='Task-1102' coro=<DynamicExtractor.gather_listings.<locals>._bounded_process() running at /home/softverse/FR-realestate-scraping/realestate_scraper/scraper/extractors/dynamic_extractor.py:136> wait_for=<Future pending cb=[Task.task_wakeup()]> cb=[as_completed.<locals>._on_completion() at /usr/lib/python3.12/asyncio/tasks.py:618, <2 more>, ProtocolCallback.__init__.<locals>.cb() at /home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py:230]>
^C
(venv) softverse@Softverse:~/FR-realestate-scraping/realestate_scraper$ ^C





 realestate_scraper/scraper/extractors/dynamic_extractor.py | 17 +++++++++++------
 realestate_scraper/scraper/extractors/pipeline_extract.py  | 35 +++++++++++++++++++++++++++++++++++
 realestate_scraper/scraper/extractors/static_extractor.py  | 18 +++++++++++-------
 3 files changed, 57 insertions(+), 13 deletions(-)
(venv) softverse@Softverse:~/FR-realestate-scraping$ cd realestate_scraper
python -m scraper --reset-checkpoint
04:12:27 INFO    scraper.domain_loader | input loaded: 38 unique domains, 0 rows without website
04:12:27 INFO    scraper.pipeline | loaded 38 jobs (38 pending after checkpoint)
04:12:29 INFO    scraper.pipeline | start beausejour-immobilier.fr
04:12:30 INFO    scraper.pipeline | start rhpatrimoine.com
04:12:30 INFO    scraper.pipeline | start maxihome.net
04:12:30 INFO    scraper.pipeline | start capwestresidence.fr
04:12:30 INFO    scraper.pipeline | start zelidom.fr
04:12:30 INFO    scraper.pipeline | start maisonsoxygene.com
04:12:30 INFO    scraper.pipeline | start pietrapolis.fr
04:12:30 INFO    scraper.pipeline | start stephaneplazaimmobilier.com
04:12:30 INFO    scraper.pipeline | start nestenn.com
04:12:30 INFO    scraper.pipeline | start agencealbert1er.fr
04:12:30 INFO    scraper.pipeline | start cosialis.fr
04:12:30 INFO    scraper.pipeline | start igor-immobilier.com
04:12:34 INFO    scraper.pipeline | done beausejour-immobilier.fr status=failed listings=0 strategy=none reason=site_not_reachable in 4.8s
04:12:34 INFO    scraper.pipeline | start carmen-immobilier.com
04:12:38 INFO    scraper.extractors.static_extractor | static: no candidate listings for capwestresidence.fr
04:12:44 INFO    scraper.extractors.dynamic_extractor | dynamic: maisonsoxygene.com -> 14 candidate listing URLs
04:12:45 INFO    scraper.extractors.dynamic_extractor | dynamic: rhpatrimoine.com -> 120 candidate listing URLs
04:12:47 INFO    scraper.extractors.dynamic_extractor | dynamic: no candidate listings for stephaneplazaimmobilier.com
04:12:47 INFO    scraper.pipeline | done stephaneplazaimmobilier.com status=failed listings=0 strategy=none reason=blocked_403 in 17.8s
04:12:47 INFO    scraper.pipeline | start sporting-immobilier.fr
04:12:51 INFO    scraper.extractors.dynamic_extractor | dynamic: cosialis.fr -> 120 candidate listing URLs
04:12:51 INFO    scraper.extractors.dynamic_extractor | dynamic: no candidate listings for capwestresidence.fr
04:12:51 INFO    scraper.pipeline | done capwestresidence.fr status=failed listings=0 strategy=static reason=no_listings_found in 21.4s
04:12:51 INFO    scraper.pipeline | start mg-immobilier.com
04:12:52 INFO    scraper.extractors.static_extractor | static: maxihome.net -> 120 candidate listing URLs
04:12:53 INFO    scraper.extractors.dynamic_extractor | dynamic: pietrapolis.fr -> 2 candidate listing URLs
04:12:55 INFO    scraper.extractors.dynamic_extractor | dynamic: agencealbert1er.fr -> 9 candidate listing URLs
04:12:59 INFO    scraper.extractors.dynamic_extractor | dynamic: nestenn.com -> 40 candidate listing URLs
04:13:00 INFO    scraper.extractors.static_extractor | static: no candidate listings for maisonsoxygene.com
04:13:00 INFO    scraper.pipeline | done maisonsoxygene.com status=failed listings=0 strategy=none reason=no_listings_found in 30.1s
04:13:00 INFO    scraper.pipeline | start agencedeneuville.com
04:13:02 INFO    scraper.pipeline | done igor-immobilier.com status=failed listings=0 strategy=none reason=site_not_reachable in 32.1s
04:13:02 INFO    scraper.pipeline | start agencegrossi.com
04:14:42 WARNING scraper.pipeline | domain rhpatrimoine.com timed out
04:14:42 WARNING scraper.pipeline | domain maxihome.net timed out
04:14:42 WARNING scraper.pipeline | domain pietrapolis.fr timed out
04:14:42 WARNING scraper.pipeline | domain nestenn.com timed out
04:14:42 WARNING scraper.pipeline | domain agencealbert1er.fr timed out
04:14:42 WARNING scraper.pipeline | domain cosialis.fr timed out
04:14:42 WARNING scraper.pipeline | domain agencegrossi.com timed out
04:14:42 INFO    scraper.pipeline | done rhpatrimoine.com status=failed listings=0 strategy=none reason=site_not_reachable in 132.2s
04:14:42 INFO    scraper.pipeline | start well-estate.fr
04:14:42 INFO    scraper.pipeline | done maxihome.net status=failed listings=0 strategy=none reason=site_not_reachable in 132.2s
04:14:42 INFO    scraper.pipeline | start groupecif.com
04:14:42 INFO    scraper.pipeline | done pietrapolis.fr status=failed listings=0 strategy=none reason=site_not_reachable in 132.1s
04:14:42 INFO    scraper.pipeline | start erafrance.com
04:14:42 INFO    scraper.pipeline | done nestenn.com status=failed listings=0 strategy=none reason=site_not_reachable in 132.1s
04:14:42 INFO    scraper.pipeline | start erapontdelarc.com
04:14:42 INFO    scraper.pipeline | done agencealbert1er.fr status=failed listings=0 strategy=none reason=site_not_reachable in 132.1s
04:14:42 INFO    scraper.pipeline | start agencecoullaud.fr
04:14:42 INFO    scraper.pipeline | done cosialis.fr status=failed listings=0 strategy=none reason=site_not_reachable in 132.1s
04:14:42 INFO    scraper.pipeline | start wretmanestate.com
04:14:42 INFO    scraper.pipeline | done agencegrossi.com status=failed listings=0 strategy=none reason=site_not_reachable in 100.0s
04:14:42 INFO    scraper.pipeline | start aio-immobiliere.com
04:14:42 INFO    scraper.pipeline | done mg-immobilier.com status=failed listings=0 strategy=none reason=site_not_reachable in 110.7s
04:14:42 INFO    scraper.pipeline | start 2m-immo.com
04:14:42 INFO    scraper.pipeline | done carmen-immobilier.com status=failed listings=0 strategy=none reason=site_not_reachable in 127.4s
04:14:42 INFO    scraper.pipeline | start novilis.fr
04:16:16 WARNING scraper.pipeline | domain wretmanestate.com timed out
04:16:16 WARNING scraper.pipeline | domain agencecoullaud.fr timed out
04:16:16 WARNING scraper.pipeline | domain groupecif.com timed out
04:16:16 WARNING scraper.pipeline | domain 2m-immo.com timed out
04:16:16 WARNING scraper.pipeline | domain well-estate.fr timed out
04:16:16 INFO    scraper.pipeline | done wretmanestate.com status=failed listings=0 strategy=none reason=site_not_reachable in 94.1s
04:16:16 INFO    scraper.pipeline | start agencedesflots.com
04:16:16 WARNING scraper.pipeline | domain aio-immobiliere.com timed out
04:16:16 WARNING scraper.pipeline | domain sporting-immobilier.fr timed out
04:16:16 INFO    scraper.pipeline | done agencecoullaud.fr status=failed listings=0 strategy=none reason=site_not_reachable in 94.1s
04:16:16 INFO    scraper.pipeline | start agencemathieu.fr
04:16:16 INFO    scraper.pipeline | done groupecif.com status=failed listings=0 strategy=none reason=site_not_reachable in 94.2s
04:16:16 INFO    scraper.pipeline | start immoso.fr
04:16:16 INFO    scraper.pipeline | done 2m-immo.com status=failed listings=0 strategy=none reason=site_not_reachable in 94.1s
04:16:16 INFO    scraper.pipeline | start vancia-immobilier.fr
04:16:16 INFO    scraper.pipeline | done well-estate.fr status=failed listings=0 strategy=none reason=site_not_reachable in 94.2s
04:16:16 INFO    scraper.pipeline | start lgo-immobilier.fr
04:16:16 INFO    scraper.pipeline | done aio-immobiliere.com status=failed listings=0 strategy=none reason=site_not_reachable in 94.1s
04:16:16 INFO    scraper.pipeline | start groupimmo.pro
04:16:16 INFO    scraper.pipeline | done sporting-immobilier.fr status=failed listings=0 strategy=none reason=site_not_reachable in 208.6s
04:16:16 INFO    scraper.pipeline | start grisel-immobilier.fr
04:18:06 WARNING scraper.pipeline | domain agencedesflots.com timed out
04:18:06 INFO    scraper.pipeline | done agencedesflots.com status=failed listings=0 strategy=none reason=site_not_reachable in 110.0s
04:18:06 INFO    scraper.pipeline | start immobiliere-de-croix.com
04:18:08 INFO    scraper.extractors.dynamic_extractor | dynamic: zelidom.fr -> 37 candidate listing URLs
04:19:54 WARNING scraper.pipeline | domain immobiliere-de-croix.com timed out
04:19:54 INFO    scraper.pipeline | done immobiliere-de-croix.com status=failed listings=0 strategy=none reason=site_not_reachable in 108.6s
04:19:54 INFO    scraper.pipeline | start imbs-immo.com
04:19:55 ERROR   asyncio | Future exception was never retrieved
future: <Future finished exception=TargetClosedError('Target page, context or browser has been closed\nCall log:\n  - navigating to "https://www.rhpatrimoine.com/vente/appartement-t1-1-piece-bordeaux-33100,VA3046", waiting until "domcontentloaded"\n')>
playwright._impl._errors.TargetClosedError: Target page, context or browser has been closed
Call log:
  - navigating to "https://www.rhpatrimoine.com/vente/appartement-t1-1-piece-bordeaux-33100,VA3046", waiting until "domcontentloaded"

04:21:25 WARNING scraper.pipeline | domain imbs-immo.com timed out
04:21:25 INFO    scraper.pipeline | done imbs-immo.com status=failed listings=0 strategy=none reason=site_not_reachable in 90.3s
04:21:25 INFO    scraper.pipeline | start tit-immobilier.com
04:22:56 WARNING scraper.pipeline | domain tit-immobilier.com timed out
04:22:56 INFO    scraper.pipeline | done tit-immobilier.com status=failed listings=0 strategy=none reason=site_not_reachable in 90.8s
04:22:56 INFO    scraper.pipeline | start jeminstalleici.com
04:22:56 INFO    scraper.pipeline | done agencemathieu.fr status=failed listings=0 strategy=none reason=site_not_reachable in 399.7s
04:22:56 INFO    scraper.pipeline | start piriac-immobilier.fr
04:22:56 INFO    scraper.pipeline | done lgo-immobilier.fr status=failed listings=0 strategy=none reason=site_not_reachable in 399.6s
04:24:43 WARNING scraper.pipeline | domain jeminstalleici.com timed out
^C^C^C04:26:35 INFO    scraper.extractors.static_extractor | static: immoso.fr -> 24 candidate listing URLs
04:26:35 INFO    scraper.pipeline | done groupimmo.pro status=failed listings=0 strategy=none reason=site_not_reachable in 618.7s
04:26:35 INFO    scraper.pipeline | done grisel-immobilier.fr status=failed listings=0 strategy=none reason=site_not_reachable in 618.7s
04:26:35 WARNING asyncio | pipe closed by peer or os.write(pipe, data) raised exception.
04:26:35 WARNING asyncio | pipe closed by peer or os.write(pipe, data) raised exception.
04:26:35 WARNING asyncio | pipe closed by peer or os.write(pipe, data) raised exception.
04:26:35 WARNING asyncio | pipe closed by peer or os.write(pipe, data) raised exception.
04:26:35 WARNING asyncio | pipe closed by peer or os.write(pipe, data) raised exception.
04:26:35 WARNING asyncio | pipe closed by peer or os.write(pipe, data) raised exception.
04:26:35 WARNING asyncio | pipe closed by peer or os.write(pipe, data) raised exception.
04:26:35 WARNING asyncio | pipe closed by peer or os.write(pipe, data) raised exception.
04:26:35 WARNING asyncio | pipe closed by peer or os.write(pipe, data) raised exception.
04:26:35 WARNING asyncio | pipe closed by peer or os.write(pipe, data) raised exception.
04:26:35 WARNING asyncio | pipe closed by peer or os.write(pipe, data) raised exception.
04:26:35 WARNING asyncio | pipe closed by peer or os.write(pipe, data) raised exception.
04:26:35 WARNING asyncio | pipe closed by peer or os.write(pipe, data) raised exception.
04:26:35 WARNING asyncio | pipe closed by peer or os.write(pipe, data) raised exception.
04:26:35 WARNING asyncio | pipe closed by peer or os.write(pipe, data) raised exception.
04:26:35 WARNING asyncio | pipe closed by peer or os.write(pipe, data) raised exception.
04:26:35 WARNING asyncio | pipe closed by peer or os.write(pipe, data) raised exception.
04:26:35 WARNING asyncio | pipe closed by peer or os.write(pipe, data) raised exception.
04:26:35 WARNING asyncio | pipe closed by peer or os.write(pipe, data) raised exception.
04:26:35 WARNING asyncio | pipe closed by peer or os.write(pipe, data) raised exception.
04:26:35 WARNING asyncio | pipe closed by peer or os.write(pipe, data) raised exception.
04:26:35 WARNING asyncio | pipe closed by peer or os.write(pipe, data) raised exception.
04:26:35 WARNING asyncio | pipe closed by peer or os.write(pipe, data) raised exception.
04:26:35 WARNING asyncio | pipe closed by peer or os.write(pipe, data) raised exception.
04:26:35 WARNING asyncio | pipe closed by peer or os.write(pipe, data) raised exception.
04:26:35 WARNING asyncio | pipe closed by peer or os.write(pipe, data) raised exception.
04:26:35 WARNING asyncio | pipe closed by peer or os.write(pipe, data) raised exception.
04:26:35 WARNING asyncio | pipe closed by peer or os.write(pipe, data) raised exception.
04:26:35 WARNING asyncio | pipe closed by peer or os.write(pipe, data) raised exception.
04:26:35 WARNING asyncio | pipe closed by peer or os.write(pipe, data) raised exception.
04:26:35 WARNING asyncio | pipe closed by peer or os.write(pipe, data) raised exception.
04:26:35 WARNING asyncio | pipe closed by peer or os.write(pipe, data) raised exception.
04:26:35 WARNING asyncio | pipe closed by peer or os.write(pipe, data) raised exception.
04:26:35 WARNING asyncio | pipe closed by peer or os.write(pipe, data) raised exception.
04:26:35 WARNING asyncio | pipe closed by peer or os.write(pipe, data) raised exception.
04:26:35 WARNING asyncio | pipe closed by peer or os.write(pipe, data) raised exception.
Error occurred in event listener
Traceback (most recent call last):
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_browser_context.py", line 246, in _on_route
    handled = await route_handler.handle(route)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 435, in handle
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 422, in handle
    return await self._handle_internal(route)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 463, in _handle_internal
    await asyncio.ensure_future(coro_or_future)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/scraper/browser_pool.py", line 232, in _route_handler
    await route.continue_()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/async_api/_generated.py", line 969, in continue_
    await self._impl_obj.continue_(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 513, in continue_
    return await self._handle_route(_inner)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 463, in _handle_route
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 459, in _handle_route
    await callback()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 511, in _inner
    await self._inner_continue(False)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 517, in _inner_continue
    await self._race_with_page_close(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 558, in _race_with_page_close
    raise cast(BaseException, fut.exception())
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 69, in send
    return await self._connection.wrap_api_call(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 559, in wrap_api_call
    raise rewrite_error(error, f"{parsed_st['apiName']}: {error}") from None
Exception: Route.continue_: Connection closed while reading from the driver
Error occurred in event listener
Traceback (most recent call last):
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_browser_context.py", line 246, in _on_route
    handled = await route_handler.handle(route)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 435, in handle
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 422, in handle
    return await self._handle_internal(route)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 463, in _handle_internal
    await asyncio.ensure_future(coro_or_future)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/scraper/browser_pool.py", line 232, in _route_handler
    await route.continue_()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/async_api/_generated.py", line 969, in continue_
    await self._impl_obj.continue_(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 513, in continue_
    return await self._handle_route(_inner)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 463, in _handle_route
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 459, in _handle_route
    await callback()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 511, in _inner
    await self._inner_continue(False)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 517, in _inner_continue
    await self._race_with_page_close(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 558, in _race_with_page_close
    raise cast(BaseException, fut.exception())
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 69, in send
    return await self._connection.wrap_api_call(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 559, in wrap_api_call
    raise rewrite_error(error, f"{parsed_st['apiName']}: {error}") from None
Exception: Route.continue_: Connection closed while reading from the driver
Error occurred in event listener
Traceback (most recent call last):
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_browser_context.py", line 246, in _on_route
    handled = await route_handler.handle(route)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 435, in handle
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 422, in handle
    return await self._handle_internal(route)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 463, in _handle_internal
    await asyncio.ensure_future(coro_or_future)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/scraper/browser_pool.py", line 232, in _route_handler
    await route.continue_()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/async_api/_generated.py", line 969, in continue_
    await self._impl_obj.continue_(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 513, in continue_
    return await self._handle_route(_inner)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 463, in _handle_route
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 459, in _handle_route
    await callback()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 511, in _inner
    await self._inner_continue(False)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 517, in _inner_continue
    await self._race_with_page_close(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 558, in _race_with_page_close
    raise cast(BaseException, fut.exception())
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 69, in send
    return await self._connection.wrap_api_call(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 559, in wrap_api_call
    raise rewrite_error(error, f"{parsed_st['apiName']}: {error}") from None
Exception: Route.continue_: Connection closed while reading from the driver
Error occurred in event listener
Traceback (most recent call last):
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_browser_context.py", line 246, in _on_route
    handled = await route_handler.handle(route)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 435, in handle
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 422, in handle
    return await self._handle_internal(route)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 463, in _handle_internal
    await asyncio.ensure_future(coro_or_future)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/scraper/browser_pool.py", line 232, in _route_handler
    await route.continue_()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/async_api/_generated.py", line 969, in continue_
    await self._impl_obj.continue_(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 513, in continue_
    return await self._handle_route(_inner)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 463, in _handle_route
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 459, in _handle_route
    await callback()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 511, in _inner
    await self._inner_continue(False)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 517, in _inner_continue
    await self._race_with_page_close(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 558, in _race_with_page_close
    raise cast(BaseException, fut.exception())
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 69, in send
    return await self._connection.wrap_api_call(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 559, in wrap_api_call
    raise rewrite_error(error, f"{parsed_st['apiName']}: {error}") from None
Exception: Route.continue_: Connection closed while reading from the driver
Error occurred in event listener
Traceback (most recent call last):
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_browser_context.py", line 246, in _on_route
    handled = await route_handler.handle(route)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 435, in handle
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 422, in handle
    return await self._handle_internal(route)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 463, in _handle_internal
    await asyncio.ensure_future(coro_or_future)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/scraper/browser_pool.py", line 232, in _route_handler
    await route.continue_()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/async_api/_generated.py", line 969, in continue_
    await self._impl_obj.continue_(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 513, in continue_
    return await self._handle_route(_inner)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 463, in _handle_route
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 459, in _handle_route
    await callback()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 511, in _inner
    await self._inner_continue(False)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 517, in _inner_continue
    await self._race_with_page_close(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 558, in _race_with_page_close
    raise cast(BaseException, fut.exception())
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 69, in send
    return await self._connection.wrap_api_call(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 559, in wrap_api_call
    raise rewrite_error(error, f"{parsed_st['apiName']}: {error}") from None
Exception: Route.continue_: Connection closed while reading from the driver
Error occurred in event listener
Traceback (most recent call last):
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_browser_context.py", line 246, in _on_route
    handled = await route_handler.handle(route)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 435, in handle
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 422, in handle
    return await self._handle_internal(route)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 463, in _handle_internal
    await asyncio.ensure_future(coro_or_future)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/scraper/browser_pool.py", line 232, in _route_handler
    await route.continue_()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/async_api/_generated.py", line 969, in continue_
    await self._impl_obj.continue_(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 513, in continue_
    return await self._handle_route(_inner)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 463, in _handle_route
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 459, in _handle_route
    await callback()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 511, in _inner
    await self._inner_continue(False)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 517, in _inner_continue
    await self._race_with_page_close(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 558, in _race_with_page_close
    raise cast(BaseException, fut.exception())
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 69, in send
    return await self._connection.wrap_api_call(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 559, in wrap_api_call
    raise rewrite_error(error, f"{parsed_st['apiName']}: {error}") from None
Exception: Route.continue_: Connection closed while reading from the driver
Error occurred in event listener
Traceback (most recent call last):
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_browser_context.py", line 246, in _on_route
    handled = await route_handler.handle(route)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 435, in handle
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 422, in handle
    return await self._handle_internal(route)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 463, in _handle_internal
    await asyncio.ensure_future(coro_or_future)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/scraper/browser_pool.py", line 232, in _route_handler
    await route.continue_()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/async_api/_generated.py", line 969, in continue_
    await self._impl_obj.continue_(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 513, in continue_
    return await self._handle_route(_inner)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 463, in _handle_route
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 459, in _handle_route
    await callback()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 511, in _inner
    await self._inner_continue(False)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 517, in _inner_continue
    await self._race_with_page_close(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 558, in _race_with_page_close
    raise cast(BaseException, fut.exception())
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 69, in send
    return await self._connection.wrap_api_call(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 559, in wrap_api_call
    raise rewrite_error(error, f"{parsed_st['apiName']}: {error}") from None
Exception: Route.continue_: Connection closed while reading from the driver
Error occurred in event listener
Traceback (most recent call last):
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_browser_context.py", line 246, in _on_route
    handled = await route_handler.handle(route)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 435, in handle
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 422, in handle
    return await self._handle_internal(route)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 463, in _handle_internal
    await asyncio.ensure_future(coro_or_future)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/scraper/browser_pool.py", line 232, in _route_handler
    await route.continue_()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/async_api/_generated.py", line 969, in continue_
    await self._impl_obj.continue_(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 513, in continue_
    return await self._handle_route(_inner)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 463, in _handle_route
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 459, in _handle_route
    await callback()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 511, in _inner
    await self._inner_continue(False)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 517, in _inner_continue
    await self._race_with_page_close(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 558, in _race_with_page_close
    raise cast(BaseException, fut.exception())
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 69, in send
    return await self._connection.wrap_api_call(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 559, in wrap_api_call
    raise rewrite_error(error, f"{parsed_st['apiName']}: {error}") from None
Exception: Route.continue_: Connection closed while reading from the driver
Error occurred in event listener
Traceback (most recent call last):
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_browser_context.py", line 246, in _on_route
    handled = await route_handler.handle(route)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 435, in handle
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 422, in handle
    return await self._handle_internal(route)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 463, in _handle_internal
    await asyncio.ensure_future(coro_or_future)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/scraper/browser_pool.py", line 232, in _route_handler
    await route.continue_()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/async_api/_generated.py", line 969, in continue_
    await self._impl_obj.continue_(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 513, in continue_
    return await self._handle_route(_inner)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 463, in _handle_route
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 459, in _handle_route
    await callback()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 511, in _inner
    await self._inner_continue(False)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 517, in _inner_continue
    await self._race_with_page_close(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 558, in _race_with_page_close
    raise cast(BaseException, fut.exception())
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 69, in send
    return await self._connection.wrap_api_call(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 559, in wrap_api_call
    raise rewrite_error(error, f"{parsed_st['apiName']}: {error}") from None
Exception: Route.continue_: Connection closed while reading from the driver
Error occurred in event listener
Traceback (most recent call last):
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_browser_context.py", line 246, in _on_route
    handled = await route_handler.handle(route)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 435, in handle
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 422, in handle
    return await self._handle_internal(route)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 463, in _handle_internal
    await asyncio.ensure_future(coro_or_future)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/scraper/browser_pool.py", line 232, in _route_handler
    await route.continue_()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/async_api/_generated.py", line 969, in continue_
    await self._impl_obj.continue_(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 513, in continue_
    return await self._handle_route(_inner)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 463, in _handle_route
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 459, in _handle_route
    await callback()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 511, in _inner
    await self._inner_continue(False)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 517, in _inner_continue
    await self._race_with_page_close(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 558, in _race_with_page_close
    raise cast(BaseException, fut.exception())
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 69, in send
    return await self._connection.wrap_api_call(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 559, in wrap_api_call
    raise rewrite_error(error, f"{parsed_st['apiName']}: {error}") from None
Exception: Route.continue_: Connection closed while reading from the driver
Error occurred in event listener
Traceback (most recent call last):
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_browser_context.py", line 246, in _on_route
    handled = await route_handler.handle(route)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 435, in handle
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 422, in handle
    return await self._handle_internal(route)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 463, in _handle_internal
    await asyncio.ensure_future(coro_or_future)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/scraper/browser_pool.py", line 232, in _route_handler
    await route.continue_()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/async_api/_generated.py", line 969, in continue_
    await self._impl_obj.continue_(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 513, in continue_
    return await self._handle_route(_inner)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 463, in _handle_route
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 459, in _handle_route
    await callback()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 511, in _inner
    await self._inner_continue(False)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 517, in _inner_continue
    await self._race_with_page_close(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 558, in _race_with_page_close
    raise cast(BaseException, fut.exception())
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 69, in send
    return await self._connection.wrap_api_call(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 559, in wrap_api_call
    raise rewrite_error(error, f"{parsed_st['apiName']}: {error}") from None
Exception: Route.continue_: Connection closed while reading from the driver
Error occurred in event listener
Traceback (most recent call last):
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_browser_context.py", line 246, in _on_route
    handled = await route_handler.handle(route)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 435, in handle
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 422, in handle
    return await self._handle_internal(route)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 463, in _handle_internal
    await asyncio.ensure_future(coro_or_future)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/scraper/browser_pool.py", line 232, in _route_handler
    await route.continue_()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/async_api/_generated.py", line 969, in continue_
    await self._impl_obj.continue_(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 513, in continue_
    return await self._handle_route(_inner)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 463, in _handle_route
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 459, in _handle_route
    await callback()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 511, in _inner
    await self._inner_continue(False)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 517, in _inner_continue
    await self._race_with_page_close(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 558, in _race_with_page_close
    raise cast(BaseException, fut.exception())
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 69, in send
    return await self._connection.wrap_api_call(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 559, in wrap_api_call
    raise rewrite_error(error, f"{parsed_st['apiName']}: {error}") from None
Exception: Route.continue_: Connection closed while reading from the driver
Error occurred in event listener
Traceback (most recent call last):
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_browser_context.py", line 246, in _on_route
    handled = await route_handler.handle(route)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 435, in handle
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 422, in handle
    return await self._handle_internal(route)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 463, in _handle_internal
    await asyncio.ensure_future(coro_or_future)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/scraper/browser_pool.py", line 232, in _route_handler
    await route.continue_()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/async_api/_generated.py", line 969, in continue_
    await self._impl_obj.continue_(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 513, in continue_
    return await self._handle_route(_inner)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 463, in _handle_route
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 459, in _handle_route
    await callback()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 511, in _inner
    await self._inner_continue(False)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 517, in _inner_continue
    await self._race_with_page_close(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 558, in _race_with_page_close
    raise cast(BaseException, fut.exception())
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 69, in send
    return await self._connection.wrap_api_call(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 559, in wrap_api_call
    raise rewrite_error(error, f"{parsed_st['apiName']}: {error}") from None
Exception: Route.continue_: Connection closed while reading from the driver
Error occurred in event listener
Traceback (most recent call last):
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_browser_context.py", line 246, in _on_route
    handled = await route_handler.handle(route)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 435, in handle
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 422, in handle
    return await self._handle_internal(route)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 463, in _handle_internal
    await asyncio.ensure_future(coro_or_future)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/scraper/browser_pool.py", line 232, in _route_handler
    await route.continue_()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/async_api/_generated.py", line 969, in continue_
    await self._impl_obj.continue_(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 513, in continue_
    return await self._handle_route(_inner)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 463, in _handle_route
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 459, in _handle_route
    await callback()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 511, in _inner
    await self._inner_continue(False)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 517, in _inner_continue
    await self._race_with_page_close(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 558, in _race_with_page_close
    raise cast(BaseException, fut.exception())
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 69, in send
    return await self._connection.wrap_api_call(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 559, in wrap_api_call
    raise rewrite_error(error, f"{parsed_st['apiName']}: {error}") from None
Exception: Route.continue_: Connection closed while reading from the driver
Error occurred in event listener
Traceback (most recent call last):
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_browser_context.py", line 246, in _on_route
    handled = await route_handler.handle(route)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 435, in handle
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 422, in handle
    return await self._handle_internal(route)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 463, in _handle_internal
    await asyncio.ensure_future(coro_or_future)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/scraper/browser_pool.py", line 232, in _route_handler
    await route.continue_()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/async_api/_generated.py", line 969, in continue_
    await self._impl_obj.continue_(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 513, in continue_
    return await self._handle_route(_inner)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 463, in _handle_route
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 459, in _handle_route
    await callback()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 511, in _inner
    await self._inner_continue(False)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 517, in _inner_continue
    await self._race_with_page_close(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 558, in _race_with_page_close
    raise cast(BaseException, fut.exception())
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 69, in send
    return await self._connection.wrap_api_call(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 559, in wrap_api_call
    raise rewrite_error(error, f"{parsed_st['apiName']}: {error}") from None
Exception: Route.continue_: Connection closed while reading from the driver
04:26:35 WARNING asyncio | pipe closed by peer or os.write(pipe, data) raised exception.
04:26:35 WARNING asyncio | pipe closed by peer or os.write(pipe, data) raised exception.
Error occurred in event listener
Traceback (most recent call last):
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_browser_context.py", line 246, in _on_route
    handled = await route_handler.handle(route)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 435, in handle
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 422, in handle
    return await self._handle_internal(route)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 463, in _handle_internal
    await asyncio.ensure_future(coro_or_future)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/scraper/browser_pool.py", line 230, in _route_handler
    await route.continue_()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/async_api/_generated.py", line 969, in continue_
    await self._impl_obj.continue_(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 513, in continue_
    return await self._handle_route(_inner)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 463, in _handle_route
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 459, in _handle_route
    await callback()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 511, in _inner
    await self._inner_continue(False)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 517, in _inner_continue
    await self._race_with_page_close(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 558, in _race_with_page_close
    raise cast(BaseException, fut.exception())
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 69, in send
    return await self._connection.wrap_api_call(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 559, in wrap_api_call
    raise rewrite_error(error, f"{parsed_st['apiName']}: {error}") from None
Exception: Route.continue_: Connection closed while reading from the driver
Error occurred in event listener
Traceback (most recent call last):
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_browser_context.py", line 246, in _on_route
    handled = await route_handler.handle(route)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 435, in handle
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 422, in handle
    return await self._handle_internal(route)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 463, in _handle_internal
    await asyncio.ensure_future(coro_or_future)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/scraper/browser_pool.py", line 223, in _route_handler
    await route.continue_()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/async_api/_generated.py", line 969, in continue_
    await self._impl_obj.continue_(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 513, in continue_
    return await self._handle_route(_inner)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 463, in _handle_route
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 459, in _handle_route
    await callback()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 511, in _inner
    await self._inner_continue(False)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 517, in _inner_continue
    await self._race_with_page_close(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 558, in _race_with_page_close
    raise cast(BaseException, fut.exception())
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 69, in send
    return await self._connection.wrap_api_call(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 559, in wrap_api_call
    raise rewrite_error(error, f"{parsed_st['apiName']}: {error}") from None
Exception: Route.continue_: Connection closed while reading from the driver
Error occurred in event listener
Traceback (most recent call last):
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_browser_context.py", line 246, in _on_route
    handled = await route_handler.handle(route)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 435, in handle
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 422, in handle
    return await self._handle_internal(route)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 463, in _handle_internal
    await asyncio.ensure_future(coro_or_future)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/scraper/browser_pool.py", line 223, in _route_handler
    await route.continue_()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/async_api/_generated.py", line 969, in continue_
    await self._impl_obj.continue_(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 513, in continue_
    return await self._handle_route(_inner)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 463, in _handle_route
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 459, in _handle_route
    await callback()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 511, in _inner
    await self._inner_continue(False)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 517, in _inner_continue
    await self._race_with_page_close(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 558, in _race_with_page_close
    raise cast(BaseException, fut.exception())
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 69, in send
    return await self._connection.wrap_api_call(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 559, in wrap_api_call
    raise rewrite_error(error, f"{parsed_st['apiName']}: {error}") from None
Exception: Route.continue_: Connection closed while reading from the driver
Error occurred in event listener
Traceback (most recent call last):
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_browser_context.py", line 246, in _on_route
    handled = await route_handler.handle(route)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 435, in handle
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 422, in handle
    return await self._handle_internal(route)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 463, in _handle_internal
    await asyncio.ensure_future(coro_or_future)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/scraper/browser_pool.py", line 223, in _route_handler
    await route.continue_()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/async_api/_generated.py", line 969, in continue_
    await self._impl_obj.continue_(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 513, in continue_
    return await self._handle_route(_inner)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 463, in _handle_route
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 459, in _handle_route
    await callback()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 511, in _inner
    await self._inner_continue(False)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 517, in _inner_continue
    await self._race_with_page_close(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 558, in _race_with_page_close
    raise cast(BaseException, fut.exception())
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 69, in send
    return await self._connection.wrap_api_call(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 559, in wrap_api_call
    raise rewrite_error(error, f"{parsed_st['apiName']}: {error}") from None
Exception: Route.continue_: Connection closed while reading from the driver
Error occurred in event listener
Traceback (most recent call last):
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_browser_context.py", line 246, in _on_route
    handled = await route_handler.handle(route)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 435, in handle
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 422, in handle
    return await self._handle_internal(route)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 463, in _handle_internal
    await asyncio.ensure_future(coro_or_future)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/scraper/browser_pool.py", line 223, in _route_handler
    await route.continue_()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/async_api/_generated.py", line 969, in continue_
    await self._impl_obj.continue_(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 513, in continue_
    return await self._handle_route(_inner)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 463, in _handle_route
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 459, in _handle_route
    await callback()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 511, in _inner
    await self._inner_continue(False)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 517, in _inner_continue
    await self._race_with_page_close(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 558, in _race_with_page_close
    raise cast(BaseException, fut.exception())
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 69, in send
    return await self._connection.wrap_api_call(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 559, in wrap_api_call
    raise rewrite_error(error, f"{parsed_st['apiName']}: {error}") from None
Exception: Route.continue_: Connection closed while reading from the driver
Error occurred in event listener
Traceback (most recent call last):
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_browser_context.py", line 246, in _on_route
    handled = await route_handler.handle(route)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 435, in handle
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 422, in handle
    return await self._handle_internal(route)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 463, in _handle_internal
    await asyncio.ensure_future(coro_or_future)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/scraper/browser_pool.py", line 223, in _route_handler
    await route.continue_()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/async_api/_generated.py", line 969, in continue_
    await self._impl_obj.continue_(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 513, in continue_
    return await self._handle_route(_inner)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 463, in _handle_route
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 459, in _handle_route
    await callback()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 511, in _inner
    await self._inner_continue(False)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 517, in _inner_continue
    await self._race_with_page_close(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 558, in _race_with_page_close
    raise cast(BaseException, fut.exception())
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 69, in send
    return await self._connection.wrap_api_call(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 559, in wrap_api_call
    raise rewrite_error(error, f"{parsed_st['apiName']}: {error}") from None
Exception: Route.continue_: Connection closed while reading from the driver
Error occurred in event listener
Traceback (most recent call last):
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_browser_context.py", line 246, in _on_route
    handled = await route_handler.handle(route)
              ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 435, in handle
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 422, in handle
    return await self._handle_internal(route)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_helper.py", line 463, in _handle_internal
    await asyncio.ensure_future(coro_or_future)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/scraper/browser_pool.py", line 223, in _route_handler
    await route.continue_()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/async_api/_generated.py", line 969, in continue_
    await self._impl_obj.continue_(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 513, in continue_
    return await self._handle_route(_inner)
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 463, in _handle_route
    raise e
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 459, in _handle_route
    await callback()
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 511, in _inner
    await self._inner_continue(False)
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 517, in _inner_continue
    await self._race_with_page_close(
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_network.py", line 558, in _race_with_page_close
    raise cast(BaseException, fut.exception())
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 69, in send
    return await self._connection.wrap_api_call(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 559, in wrap_api_call
    raise rewrite_error(error, f"{parsed_st['apiName']}: {error}") from None
Exception: Route.continue_: Connection closed while reading from the driver
04:26:35 ERROR   asyncio | Future exception was never retrieved
future: <Future finished exception=TargetClosedError('Target page, context or browser has been closed')>
Traceback (most recent call last):
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 557, in wrap_api_call
    return await cb()
           ^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 120, in _inner_send
    callback = self._connection._send_message_to_server(
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 358, in _send_message_to_server
    raise self._closed_error
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 557, in wrap_api_call
    return await cb()
           ^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 120, in _inner_send
    callback = self._connection._send_message_to_server(
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 358, in _send_message_to_server
    raise self._closed_error
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 557, in wrap_api_call
    return await cb()
           ^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 120, in _inner_send
    callback = self._connection._send_message_to_server(
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 358, in _send_message_to_server
    raise self._closed_error
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 557, in wrap_api_call
    return await cb()
           ^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 120, in _inner_send
    callback = self._connection._send_message_to_server(
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 358, in _send_message_to_server
    raise self._closed_error
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 557, in wrap_api_call
    return await cb()
           ^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 120, in _inner_send
    callback = self._connection._send_message_to_server(
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 358, in _send_message_to_server
    raise self._closed_error
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 557, in wrap_api_call
    return await cb()
           ^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 120, in _inner_send
    callback = self._connection._send_message_to_server(
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 358, in _send_message_to_server
    raise self._closed_error
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 557, in wrap_api_call
    return await cb()
           ^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 120, in _inner_send
    callback = self._connection._send_message_to_server(
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 358, in _send_message_to_server
    raise self._closed_error
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 557, in wrap_api_call
    return await cb()
           ^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 120, in _inner_send
    callback = self._connection._send_message_to_server(
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 358, in _send_message_to_server
    raise self._closed_error
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 557, in wrap_api_call
    return await cb()
           ^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 120, in _inner_send
    callback = self._connection._send_message_to_server(
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 358, in _send_message_to_server
    raise self._closed_error
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 557, in wrap_api_call
    return await cb()
           ^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 120, in _inner_send
    callback = self._connection._send_message_to_server(
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 358, in _send_message_to_server
    raise self._closed_error
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 557, in wrap_api_call
    return await cb()
           ^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 120, in _inner_send
    callback = self._connection._send_message_to_server(
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 358, in _send_message_to_server
    raise self._closed_error
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 557, in wrap_api_call
    return await cb()
           ^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 120, in _inner_send
    callback = self._connection._send_message_to_server(
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 358, in _send_message_to_server
    raise self._closed_error
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 557, in wrap_api_call
    return await cb()
           ^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 120, in _inner_send
    callback = self._connection._send_message_to_server(
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 358, in _send_message_to_server
    raise self._closed_error
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 557, in wrap_api_call
    return await cb()
           ^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 120, in _inner_send
    callback = self._connection._send_message_to_server(
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 358, in _send_message_to_server
    raise self._closed_error
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 557, in wrap_api_call
    return await cb()
           ^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 120, in _inner_send
    callback = self._connection._send_message_to_server(
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 358, in _send_message_to_server
    raise self._closed_error
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 557, in wrap_api_call
    return await cb()
           ^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 120, in _inner_send
    callback = self._connection._send_message_to_server(
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 358, in _send_message_to_server
    raise self._closed_error
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 557, in wrap_api_call
    return await cb()
           ^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 120, in _inner_send
    callback = self._connection._send_message_to_server(
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 358, in _send_message_to_server
    raise self._closed_error
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 557, in wrap_api_call
    return await cb()
           ^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 120, in _inner_send
    callback = self._connection._send_message_to_server(
               ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 358, in _send_message_to_server
    raise self._closed_error
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 557, in wrap_api_call
    return await cb()
           ^^^^^^^^^^
  File "/home/softverse/FR-realestate-scraping/realestate_scraper/venv/lib/python3.12/site-packages/playwright/_impl/_connection.py", line 132, in _inner_send
    result = next(iter(done)).result()
             ^^^^^^^^^^^^^^^^^^^^^^^^^
playwright._impl._errors.TargetClosedError: Target page, context or browser has been closed
(venv) softverse@Softverse:~/FR-realestate-scraping/realestate_scraper$