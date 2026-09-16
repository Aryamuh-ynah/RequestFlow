from __future__ import annotations

import pycurl

from app.network.models import NetworkStage, NetworkTimings


def _duration(
    start_ms: float,
    end_ms: float,
) -> float:
    """
    Return a safe positive duration.

    Some values may be zero or identical when a stage does not apply.
    """
    return max(0.0, end_ms - start_ms)


def _time_ms(
    curl: pycurl.Curl,
    normal_name: str,
    microsecond_name: str,
) -> float:
    """
    Read libcurl timing information in milliseconds.

    Prefer the newer *_TIME_T values because they use integer
    microseconds. Fall back to the classic floating-point seconds
    values for compatibility with older libcurl/PycURL builds.
    """

    microsecond_constant = getattr(
        pycurl,
        microsecond_name,
        None,
    )

    if microsecond_constant is not None:
        value = curl.getinfo(
            microsecond_constant
        )

        return float(value) / 1000.0

    normal_constant = getattr(
        pycurl,
        normal_name,
    )

    value = curl.getinfo(
        normal_constant
    )

    return float(value) * 1000.0


def collect_network_timings(
    curl: pycurl.Curl,
) -> NetworkTimings:
    """
    Convert libcurl's cumulative timestamps into individual stages.

    libcurl values are measured from the beginning of the transfer.

    Example:

        NAMELOOKUP     = 10 ms
        CONNECT        = 30 ms
        APPCONNECT     = 80 ms
        PRETRANSFER    = 81 ms
        STARTTRANSFER  = 190 ms
        TOTAL          = 200 ms

    becomes:

        DNS            = 10 ms
        TCP            = 20 ms
        TLS            = 50 ms
        Pre-transfer   = 1 ms
        First byte     = 109 ms
        Download       = 10 ms
    """

    name_lookup = _time_ms(
        curl,
        "NAMELOOKUP_TIME",
        "NAMELOOKUP_TIME_T",
    )

    connect = _time_ms(
        curl,
        "CONNECT_TIME",
        "CONNECT_TIME_T",
    )

    app_connect = _time_ms(
        curl,
        "APPCONNECT_TIME",
        "APPCONNECT_TIME_T",
    )

    pre_transfer = _time_ms(
        curl,
        "PRETRANSFER_TIME",
        "PRETRANSFER_TIME_T",
    )

    start_transfer = _time_ms(
        curl,
        "STARTTRANSFER_TIME",
        "STARTTRANSFER_TIME_T",
    )

    total = _time_ms(
        curl,
        "TOTAL_TIME",
        "TOTAL_TIME_T",
    )

    # ---------------------------------------------------------
    # Derived stage durations
    # ---------------------------------------------------------

    dns_ms = max(
        0.0,
        name_lookup,
    )

    tcp_ms = _duration(
        name_lookup,
        connect,
    )

    has_tls = (
        app_connect > 0
        and app_connect >= connect
    )

    if has_tls:
        tls_ms = _duration(
            connect,
            app_connect,
        )

        connection_ready = app_connect

    else:
        tls_ms = 0.0
        connection_ready = connect

    pre_transfer_ms = _duration(
        connection_ready,
        pre_transfer,
    )

    first_byte_wait_ms = _duration(
        pre_transfer,
        start_transfer,
    )

    download_ms = _duration(
        start_transfer,
        total,
    )

    # ---------------------------------------------------------
    # Network endpoint
    # ---------------------------------------------------------

    primary_ip = ""

    try:
        primary_ip = str(
            curl.getinfo(
                pycurl.PRIMARY_IP
            )
            or ""
        )
    except (AttributeError, pycurl.error):
        pass

    primary_port = 0

    primary_port_constant = getattr(
        pycurl,
        "PRIMARY_PORT",
        None,
    )

    if primary_port_constant is not None:
        try:
            primary_port = int(
                curl.getinfo(
                    primary_port_constant
                )
            )
        except pycurl.error:
            pass

    # ---------------------------------------------------------
    # Stage representation
    #
    # Phase 3 will consume this directly for the visual flow.
    # ---------------------------------------------------------

    stages = (
        NetworkStage(
            key="dns",
            label="DNS Lookup",
            start_ms=0.0,
            end_ms=name_lookup,
            duration_ms=dns_ms,
        ),
        NetworkStage(
            key="tcp",
            label="TCP Connect",
            start_ms=name_lookup,
            end_ms=connect,
            duration_ms=tcp_ms,
        ),
        NetworkStage(
            key="tls",
            label="TLS Handshake",
            start_ms=connect,
            end_ms=app_connect if has_tls else connect,
            duration_ms=tls_ms,
            skipped=not has_tls,
        ),
        NetworkStage(
            key="pre_transfer",
            label="Pre-transfer",
            start_ms=connection_ready,
            end_ms=pre_transfer,
            duration_ms=pre_transfer_ms,
        ),
        NetworkStage(
            key="first_byte",
            label="Waiting for First Byte",
            start_ms=pre_transfer,
            end_ms=start_transfer,
            duration_ms=first_byte_wait_ms,
        ),
        NetworkStage(
            key="download",
            label="Download",
            start_ms=start_transfer,
            end_ms=total,
            duration_ms=download_ms,
        ),
    )

    return NetworkTimings(
        dns_ms=dns_ms,
        tcp_ms=tcp_ms,
        tls_ms=tls_ms,
        pre_transfer_ms=pre_transfer_ms,
        first_byte_wait_ms=first_byte_wait_ms,
        download_ms=download_ms,
        total_ms=total,
        name_lookup_at_ms=name_lookup,
        connect_at_ms=connect,
        app_connect_at_ms=app_connect,
        pre_transfer_at_ms=pre_transfer,
        start_transfer_at_ms=start_transfer,
        primary_ip=primary_ip,
        primary_port=primary_port,
        stages=stages,
    )