create table guilds(
    guildId     bigint      not null,
    communityId text,
    channelId   bigint,
    isMember    integer     not null    default 0,
    lastres     integer     not null    default 0,
    lastmv      integer     not null    default 0,
    lastlv        integer     not null    default 0,
    liveStatus    integer    not null   default 2,
    PRIMARY KEY(guildId)
);