using SeaEngine.CardManager;
using SeaEngine.Common;
using SeaEngine.GameDataManager;
using SeaEngine.GameDataManager.Components;
using SeaEngine.GameEffectManager;

namespace SeaEngine.RL;

public sealed record RlStatusView(string Type, int Value);

public sealed record RlCardView(
    string Uid,
    string CardId,
    string Name,
    string OwnerId,
    string Role,
    int Atk,
    int EffectiveAtk,
    int Hp,
    int MaxHp,
    bool IsPlaced,
    bool IsMoved,
    bool IsAttacked,
    int PosX,
    int PosY,
    RlStatusView[] Statuses);

public sealed record RlPlayerView(
    string Id,
    int HandCount,
    int DeckCount,
    int TrashCount,
    RlCardView[] Hand);

public sealed record RlActionView(
    string Uid,
    string EffectId,
    string Source,
    string TargetType,
    string TargetGuid,
    string TargetGuid2,
    int PosX,
    int PosY,
    string Text);

public sealed record RlObservationFrame(
    int Turn,
    string ActivePlayerId,
    string Result,
    string WinnerId,
    RlPlayerView[] Players,
    RlCardView[] Board,
    RlActionView[] Actions,
    float[] StateVector,
    float[][] ActionFeatureVectors);

public static class RlObservationExporter
{
    private static readonly string[] RoleOrder = ["Leader", "Bishop", "Knight", "Rook", "Pawn"];
    private static readonly string[] EffectBuckets = ["DeployUnit", "DefaultMove", "DefaultAttack", "TurnEnd", "Skill"];
    private static readonly string[] TargetBuckets = ["None", "Cell", "Unit", "Unit2", "Card"];
    private static readonly string[] ResultBuckets = ["Ongoing", "Player1Win", "Player2Win", "Draw"];

    public static RlObservationFrame Export(Game game, int turnCounter)
    {
        var data = game.Data;
        var playerId = data.ActivePlayerId;

        var board = data.Board.Cards.ToArray();
        var boardByUid = board.ToDictionary(card => card.Guid.ToString(), card => card);
        var actions = game.Actions.ToArray();
        var actionViews = actions.Select(BuildActionView).ToArray();
        var players = new[] { BuildPlayerView(data.Player1), BuildPlayerView(data.Player2) };

        var stateVector = BuildStateVector(data, playerId, board, actionViews, boardByUid);
        var actionFeatureVectors = actionViews.Select(action => BuildActionFeatureVector(data, playerId, board, boardByUid, action)).ToArray();

        return new RlObservationFrame(
            turnCounter,
            playerId,
            BuildResult(data),
            data.WinnerId,
            players,
            board.Select(BuildCardView).ToArray(),
            actionViews,
            stateVector,
            actionFeatureVectors
        );
    }

    private static string BuildResult(GameData data)
    {
        if (data.Winner == null) return "Ongoing";
        return data.Winner.Id == data.Player1.Id ? "Player1Win" : "Player2Win";
    }

    private static RlPlayerView BuildPlayerView(Player player)
    {
        return new RlPlayerView(
            player.Id,
            player.Hand.Count,
            player.Deck.Count,
            player.Trash.Count,
            player.Hand.Cards.Select(BuildCardView).ToArray()
        );
    }

    private static RlCardView BuildCardView(Card card)
    {
        var buffs = card.Unit.Buffs
            .Select(buff => new RlStatusView(buff.Key, buff.Value))
            .ToArray();
        var role = card.Data.UnitType.ToString();
        var effectiveAtk = card.Unit.Atk + (card.Unit.Buffs.TryGetValue("TempAtk", out var atkBuff) ? atkBuff : 0);
        return new RlCardView(
            card.Guid.ToString(),
            card.Data.Id,
            card.Data.Name,
            card.Owner.Id,
            role,
            card.Unit.Atk,
            effectiveAtk,
            card.Unit.Hp,
            card.Unit.MaxHp,
            card.Unit.IsPlaced,
            card.Unit.IsMoved,
            false,
            card.Unit.PosX,
            card.Unit.PosY,
            buffs
        );
    }

    private static RlActionView BuildActionView(GameAction action)
    {
        var targetType = action.Target.Type.ToString();
        return new RlActionView(
            action.Guid.ToString(),
            action.EffectId,
            action.Source.ToString(),
            targetType,
            action.Target.Guid.ToString(),
            action.Target.Guid2.ToString(),
            action.Target.PosX,
            action.Target.PosY,
            action.ToString()
        );
    }

    private static float[] BuildStateVector(GameData data, string playerId, Card[] board, RlActionView[] actions, Dictionary<string, Card> boardByUid)
    {
        var (_, enemyPlayer, enemyId) = GetPlayers(data, playerId);
        var (ownLeader, enemyLeader) = GetLeaders(board, playerId, enemyId);

        var ownBoard = board.Where(card => card.Owner.Id == playerId && card.Unit.IsPlaced).ToArray();
        var enemyBoard = board.Where(card => card.Owner.Id == enemyId && card.Unit.IsPlaced).ToArray();

        float ownAttackTotal = ownBoard.Sum(card => (float)card.Unit.Atk + (card.Unit.Buffs.TryGetValue("TempAtk", out var atkBuff) ? atkBuff : 0));
        float enemyAttackTotal = enemyBoard.Sum(card => (float)card.Unit.Atk + (card.Unit.Buffs.TryGetValue("TempAtk", out var atkBuff) ? atkBuff : 0));
        float ownHpTotal = ownBoard.Sum(card => (float)card.Unit.Hp);
        float enemyHpTotal = enemyBoard.Sum(card => (float)card.Unit.Hp);
        float ownReadyMove = ownBoard.Count(card => !card.Unit.IsMoved);
        float ownReadyAttack = ownBoard.Count(card => !card.Unit.IsPlaced || card.Unit.IsPlaced); // keep parity with prior Python counts
        float enemyReadyAttack = enemyBoard.Count(card => !card.Unit.IsPlaced || card.Unit.IsPlaced);
        float ownDeployable = CountDeployableCards(data, playerId, actions);
        float ownSkillActions = CountSkillActions(data, playerId, actions);
        float ownAttackActions = CountActions(data, playerId, actions, "DefaultAttack", boardByUid);
        float ownMoveActions = CountActions(data, playerId, actions, "DefaultMove", boardByUid);
        float enemyAttackersOnLeader = ownLeader is null ? 0.0f : CountAttackersOfCard(board, ownLeader);
        float ownAttackersOnEnemyLeader = enemyLeader is null ? 0.0f : CountAttackersOfCard(board, enemyLeader);
        float centerControlOwn = ownBoard.Count(card => 2 <= card.Unit.PosX && card.Unit.PosX <= 3 && 2 <= card.Unit.PosY && card.Unit.PosY <= 3);
        float centerControlEnemy = enemyBoard.Count(card => 2 <= card.Unit.PosX && card.Unit.PosX <= 3 && 2 <= card.Unit.PosY && card.Unit.PosY <= 3);

        var actionCounts = EffectBuckets.ToDictionary(bucket => bucket, _ => 0.0f);
        foreach (var action in actions)
        {
            var effectId = action.EffectId;
            var bucket = EffectBuckets.Contains(effectId) && effectId != "Skill" ? effectId : "Skill";
            actionCounts[bucket] += 1.0f;
        }
        var actionTotal = Math.Max(1.0f, actions.Length);

        var resultVector = new List<float>
        {
            NormalizeRatio(data.ActivePlayerId == null ? 0 : data.ActivePlayerId.Length, 100.0f),
            data.ActivePlayerId == playerId ? 1.0f : 0.0f,
            ..ResultOneHot(BuildResult(data))
        };

        resultVector.AddRange(new[]
        {
            NormalizeRatio(data.GetPlayer(playerId).Hand.Count, 7.0f),
            NormalizeRatio(enemyPlayer.Hand.Count, 7.0f),
            NormalizeRatio(data.GetPlayer(playerId).Deck.Count, 14.0f),
            NormalizeRatio(enemyPlayer.Deck.Count, 14.0f),
            NormalizeRatio(data.GetPlayer(playerId).Trash.Count, 14.0f),
            NormalizeRatio(enemyPlayer.Trash.Count, 14.0f),
            ownLeader == null ? 0.0f : NormalizeRatio(ownLeader.Unit.Hp, Math.Max(1.0f, ownLeader.Unit.MaxHp)),
            enemyLeader == null ? 0.0f : NormalizeRatio(enemyLeader.Unit.Hp, Math.Max(1.0f, enemyLeader.Unit.MaxHp)),
            ownLeader == null || enemyLeader == null ? 0.0f : NormalizeRatio(ownLeader.Unit.Hp - enemyLeader.Unit.Hp, Math.Max(1.0f, ownLeader.Unit.MaxHp)),
            NormalizeRatio(ownBoard.Length, 14.0f),
            NormalizeRatio(enemyBoard.Length, 14.0f),
            NormalizeRatio(ownBoard.Length - enemyBoard.Length, 14.0f),
            NormalizeRatio(ownAttackTotal, 40.0f),
            NormalizeRatio(enemyAttackTotal, 40.0f),
            NormalizeRatio(ownAttackTotal - enemyAttackTotal, 40.0f),
            NormalizeRatio(ownHpTotal, 40.0f),
            NormalizeRatio(enemyHpTotal, 40.0f),
            NormalizeRatio(ownReadyMove, 14.0f),
            NormalizeRatio(ownReadyAttack, 14.0f),
            NormalizeRatio(enemyReadyAttack, 14.0f),
            NormalizeRatio(ownDeployable, 7.0f),
            NormalizeRatio(ownSkillActions, 7.0f),
            NormalizeRatio(ownAttackActions, 20.0f),
            NormalizeRatio(ownMoveActions, 20.0f),
            NormalizeRatio(enemyAttackersOnLeader, 6.0f),
            NormalizeRatio(ownAttackersOnEnemyLeader, 6.0f),
            NormalizeRatio(centerControlOwn, 4.0f),
            NormalizeRatio(centerControlEnemy, 4.0f),
        });
        resultVector.AddRange(EffectBuckets.Select(bucket => NormalizeRatio(actionCounts[bucket], actionTotal)));

        var boardVector = BuildBoardVector(data, playerId, board, ownLeader, enemyLeader);
        var handVector = BuildHandVector(data, playerId);
        resultVector.AddRange(boardVector);
        resultVector.AddRange(handVector);
        return resultVector.ToArray();
    }

    private static float[] BuildBoardVector(GameData data, string playerId, Card[] board, Card? ownLeader, Card? enemyLeader)
    {
        var enemyId = playerId == data.Player1.Id ? data.Player2.Id : data.Player1.Id;
        var ownLx = ownLeader?.Unit.PosX ?? -1;
        var ownLy = ownLeader?.Unit.PosY ?? -1;
        var enemyLx = enemyLeader?.Unit.PosX ?? -1;
        var enemyLy = enemyLeader?.Unit.PosY ?? -1;
        var actionMap = board.Select(card => card.Guid.ToString()).ToDictionary(uid => uid, _ => new List<RlActionView>());

        var vectors = new List<float>();
        var cards = board.OrderBy(card => card.Owner.Id)
            .ThenBy(card => RoleRank(RoleFromCard(card)))
            .ThenBy(card => card.Guid.ToString())
            .ToArray();

        foreach (var card in cards.Take(14))
        {
            var (attackMod, hasMoveLock, hasAttackLock, timedStatusCount) = StatusSummary(card);
            var cx = card.Unit.PosX;
            var cy = card.Unit.PosY;
            var role = RoleFromCard(card);
            var hp = card.Unit.Hp;
            var maxHp = Math.Max(1, card.Unit.MaxHp);
            var effectiveAtk = card.Unit.Atk + (card.Unit.Buffs.TryGetValue("TempAtk", out var atkBuff) ? atkBuff : 0);
            var baseAtk = card.Unit.Atk;
            var reachableTargets = CountReadyAttackTargets(board, card);
            var adjacentEnemies = CountEnemyNeighbors(board, card);
            var incomingAttackers = CountAttackersOfCard(board, card);
            var hasAttackAction = 0.0f;
            var hasMoveAction = 0.0f;
            var threatensEnemyLeader = enemyLeader != null && Distance(cx, cy, enemyLx, enemyLy) is >= 0 and <= 0.2f ? 1.0f : 0.0f;
            var inCenter = 2 <= cx && cx <= 3 && 2 <= cy && cy <= 3 ? 1.0f : 0.0f;
            var rowProgress = card.Unit.IsPlaced
                ? NormalizeRatio(card.Owner.Id == "P1" ? cx : (Board.BoardSize - 1 - cx), Board.BoardSize - 1)
                : 0.0f;

            vectors.AddRange(new[]
            {
                card.Owner.Id == playerId ? 1.0f : -1.0f,
                card.Unit.IsPlaced ? 1.0f : 0.0f,
                card.Unit.IsMoved ? 1.0f : 0.0f,
                0.0f,
                NormalizePos(cx),
                NormalizePos(cy),
                NormalizeRatio(hp, maxHp),
                NormalizeRatio(maxHp, 10.0f),
                NormalizeRatio(baseAtk, 10.0f),
                NormalizeRatio(effectiveAtk, 10.0f),
                NormalizeRatio(attackMod, 5.0f),
                hasMoveLock,
                hasAttackLock,
                NormalizeRatio(timedStatusCount, 4.0f),
                Distance(cx, cy, ownLx, ownLy),
                Distance(cx, cy, enemyLx, enemyLy),
                NormalizeRatio(reachableTargets, 6.0f),
                NormalizeRatio(adjacentEnemies, 6.0f),
                NormalizeRatio(incomingAttackers, 6.0f),
                hasAttackAction,
                hasMoveAction,
                threatensEnemyLeader,
                inCenter,
                rowProgress,
                ..RoleOneHot(role)
            });
        }

        var missingSlots = 14 - Math.Min(cards.Length, 14);
        if (missingSlots > 0)
        {
            for (var i = 0; i < missingSlots * 29; i++)
            {
                vectors.Add(0.0f);
            }
        }

        return vectors.ToArray();
    }

    private static float[] BuildHandVector(GameData data, string playerId)
    {
        var player = data.GetPlayer(playerId);
        var hand = player.Hand.Cards.ToArray();
        var vectors = new List<float>();
        foreach (var card in hand.Take(7))
        {
            var role = RoleFromCard(card);
            var cardId = card.Data.Id;
            var deployable = 0.0f;
            var skillUsable = 0.0f;
            vectors.AddRange(new[]
            {
                1.0f,
                cardId.StartsWith("Or_") ? 1.0f : 0.0f,
                cardId.StartsWith("Cl_") ? 1.0f : 0.0f,
                deployable,
                skillUsable,
                ..RoleOneHot(role)
            });
        }
        var missingSlots = 7 - Math.Min(hand.Length, 7);
        if (missingSlots > 0)
        {
            for (var i = 0; i < missingSlots * 10; i++)
            {
                vectors.Add(0.0f);
            }
        }
        return vectors.ToArray();
    }

    private static float[] BuildActionFeatureVector(GameData data, string playerId, Card[] board, Dictionary<string, Card> boardByUid, RlActionView action)
    {
        var (_, _, enemyId) = GetPlayers(data, playerId);
        var ownLeader = GetLeaders(board, playerId, enemyId).own;
        var enemyLeader = GetLeaders(board, playerId, enemyId).enemy;

        var effectId = action.EffectId;
        var targetType = action.TargetType;
        var source = boardByUid.TryGetValue(action.Source, out var src) ? src : null;
        var targetCard = (targetType is "Unit" or "Card") && boardByUid.TryGetValue(action.TargetGuid, out var tgt) ? tgt : null;
        var targetCard2 = targetType == "Unit2" && boardByUid.TryGetValue(action.TargetGuid2, out var tgt2) ? tgt2 : null;

        var targetX = action.PosX;
        var targetY = action.PosY;
        var sourceX = source?.Unit.PosX ?? -1;
        var sourceY = source?.Unit.PosY ?? -1;
        var enemyLx = enemyLeader?.Unit.PosX ?? -1;
        var enemyLy = enemyLeader?.Unit.PosY ?? -1;

        var (attackMod, hasMoveLock, hasAttackLock, timedStatusCount) = source != null ? StatusSummary(source) : (0.0f, 0.0f, 0.0f, 0.0f);
        var sourceRole = source != null ? RoleFromCard(source) : "";
        var targetRole = targetCard != null ? RoleFromCard(targetCard) : "";
        var sourceAdjacentEnemies = source != null ? CountEnemyNeighbors(board, source) : 0.0f;
        var targetIncomingAttackers = targetCard != null ? CountAttackersOfCard(board, targetCard) : 0.0f;

        var moveDistanceBefore = Distance(sourceX, sourceY, enemyLx, enemyLy);
        var moveDistanceAfter = targetType == "Cell" ? Distance(targetX, targetY, enemyLx, enemyLy) : moveDistanceBefore;
        var movesCloser = moveDistanceAfter >= 0 && moveDistanceBefore >= 0 && moveDistanceAfter < moveDistanceBefore ? 1.0f : 0.0f;
        var entersLeaderZone = targetType == "Cell" && moveDistanceAfter >= 0 && moveDistanceAfter <= 0.2f ? 1.0f : 0.0f;

        var targetHp = targetCard?.Unit.Hp ?? 0.0f;
        var targetMaxHp = Math.Max(1.0f, targetCard?.Unit.MaxHp ?? 1.0f);
        var sourceAtk = source?.Unit.Atk + (source?.Unit.Buffs.TryGetValue("TempAtk", out var atkBuff) == true ? atkBuff : 0) ?? 0.0f;
        var canKillTarget = targetCard != null && sourceAtk >= targetHp && targetHp > 0 ? 1.0f : 0.0f;
        var threatensEnemyLeader = targetCard != null && targetCard.Owner.Id != playerId && targetRole == "Leader" ? 1.0f : 0.0f;
        var affectsTwoUnits = targetCard2 != null ? 1.0f : 0.0f;
        var sourceSurvivesTrade = targetCard != null && source != null && (targetCard.Unit.Atk + (targetCard.Unit.Buffs.TryGetValue("TempAtk", out var targetAtkBuff) ? targetAtkBuff : 0)) < source.Unit.Hp ? 1.0f : 0.0f;
        var targetIsLowHp = targetCard != null && targetHp <= 2.0f ? 1.0f : 0.0f;
        var sourceFromHand = source != null && !source.Unit.IsPlaced ? 1.0f : 0.0f;

        var vectors = new List<float>();
        vectors.AddRange(EffectOneHot(effectId));
        vectors.AddRange(TargetOneHot(targetType));
        vectors.AddRange(new[]
        {
            effectId == "TurnEnd" ? 1.0f : 0.0f,
            effectId == "DeployUnit" ? 1.0f : 0.0f,
            effectId == "DefaultMove" ? 1.0f : 0.0f,
            effectId == "DefaultAttack" ? 1.0f : 0.0f,
            source == null ? 0.0f : (source.Owner.Id == playerId ? 1.0f : -1.0f),
            source == null ? 0.0f : NormalizeRatio(source.Unit.Atk, 10.0f),
            source == null ? 0.0f : NormalizeRatio(sourceAtk, 10.0f),
            source == null ? 0.0f : NormalizeRatio(source.Unit.Hp, Math.Max(1.0f, source.Unit.MaxHp)),
            NormalizeRatio(attackMod, 5.0f),
            hasMoveLock,
            hasAttackLock,
            NormalizeRatio(timedStatusCount, 4.0f),
        });
        vectors.AddRange(RoleOneHot(sourceRole));
        vectors.AddRange(new[]
        {
            targetCard == null ? 0.0f : (targetCard.Owner.Id != playerId ? 1.0f : -1.0f),
            targetCard == null ? 0.0f : NormalizeRatio(targetCard.Unit.Atk + (targetCard.Unit.Buffs.TryGetValue("TempAtk", out var targetAtkBuff2) ? targetAtkBuff2 : 0), 10.0f),
            targetCard == null ? 0.0f : NormalizeRatio(targetHp, targetMaxHp),
            targetCard == null ? 0.0f : (targetRole == "Leader" ? 1.0f : 0.0f),
        });
        vectors.AddRange(RoleOneHot(targetRole));
        vectors.AddRange(new[]
        {
            NormalizePos(sourceX),
            NormalizePos(sourceY),
            NormalizePos(targetX),
            NormalizePos(targetY),
            moveDistanceBefore >= 0 ? moveDistanceBefore : 0.0f,
            moveDistanceAfter >= 0 ? moveDistanceAfter : 0.0f,
            movesCloser,
            entersLeaderZone,
            canKillTarget,
            threatensEnemyLeader,
            affectsTwoUnits,
            sourceSurvivesTrade,
            targetIsLowHp,
            sourceFromHand,
            NormalizeRatio(sourceAdjacentEnemies, 6.0f),
            NormalizeRatio(targetIncomingAttackers, 6.0f),
        });
        return vectors.ToArray();
    }

    private static (Player own, Player enemy, string enemyId) GetPlayers(GameData data, string playerId)
    {
        var enemyId = data.Player1.Id == playerId ? data.Player2.Id : data.Player1.Id;
        return (data.GetPlayer(playerId), data.GetPlayer(enemyId), enemyId);
    }

    private static (Card? own, Card? enemy) GetLeaders(Card[] board, string playerId, string enemyId)
    {
        Card? own = null;
        Card? enemy = null;
        foreach (var card in board)
        {
            if (!card.Unit.IsPlaced) continue;
            if (RoleFromCard(card) != "Leader") continue;
            if (card.Owner.Id == playerId) own = card;
            else if (card.Owner.Id == enemyId) enemy = card;
        }
        return (own, enemy);
    }

    private static float CountDeployableCards(GameData data, string playerId, RlActionView[] actions)
    {
        var player = data.GetPlayer(playerId);
        var deployable = 0.0f;
        foreach (var card in player.Hand.Cards)
        {
            var uid = card.Guid.ToString();
            if (actions.Any(action => action.EffectId == "DeployUnit" && action.Source == uid))
            {
                deployable += 1.0f;
            }
        }
        return deployable;
    }

    private static float CountSkillActions(GameData data, string playerId, RlActionView[] actions)
    {
        var player = data.GetPlayer(playerId);
        var handUids = player.Hand.Cards.Select(card => card.Guid.ToString()).ToHashSet();
        var count = 0.0f;
        foreach (var action in actions)
        {
            if (action.EffectId is not ("DeployUnit" or "DefaultMove" or "DefaultAttack" or "TurnEnd") && handUids.Contains(action.Source))
            {
                count += 1.0f;
            }
        }
        return count;
    }

    private static float CountActions(GameData data, string playerId, RlActionView[] actions, string effectId, Dictionary<string, Card> boardByUid)
    {
        var count = 0.0f;
        foreach (var action in actions)
        {
            if (boardByUid.TryGetValue(action.Source, out var sourceCard) && sourceCard.Owner.Id != playerId)
            {
                continue;
            }
            if (action.EffectId == effectId)
            {
                count += 1.0f;
            }
        }
        return count;
    }

    private static float CountAttackersOfCard(Card[] board, Card targetCard)
    {
        if (!targetCard.Unit.IsPlaced) return 0.0f;
        var tx = targetCard.Unit.PosX;
        var ty = targetCard.Unit.PosY;
        var targetOwner = targetCard.Owner.Id;
        var attackers = 0.0f;
        foreach (var other in board)
        {
            if (!other.Unit.IsPlaced || other.Owner.Id == targetOwner) continue;
            var ox = other.Unit.PosX;
            var oy = other.Unit.PosY;
            if (ox < 0 || oy < 0) continue;
            if (Math.Abs(ox - tx) <= 1 && Math.Abs(oy - ty) <= 1)
            {
                attackers += 1.0f;
            }
        }
        return attackers;
    }

    private static float CountReadyAttackTargets(Card[] board, Card card)
    {
        if (!card.Unit.IsPlaced) return 0.0f;
        var sourceOwner = card.Owner.Id;
        var sx = card.Unit.PosX;
        var sy = card.Unit.PosY;
        if (sx < 0 || sy < 0) return 0.0f;
        var reachable = 0.0f;
        foreach (var other in board)
        {
            if (!other.Unit.IsPlaced || other.Owner.Id == sourceOwner) continue;
            var ox = other.Unit.PosX;
            var oy = other.Unit.PosY;
            if (ox < 0 || oy < 0) continue;
            if (Math.Abs(sx - ox) <= 1 && Math.Abs(sy - oy) <= 1)
            {
                reachable += 1.0f;
            }
        }
        return reachable;
    }

    private static float CountEnemyNeighbors(Card[] board, Card card) => CountReadyAttackTargets(board, card);

    private static (float attackMod, float hasMoveLock, float hasAttackLock, float timedStatusCount) StatusSummary(Card card)
    {
        var attackMod = 0.0f;
        var hasMoveLock = 0.0f;
        var hasAttackLock = 0.0f;
        var timedStatusCount = 0.0f;
        foreach (var status in card.Unit.Buffs)
        {
            timedStatusCount += 1.0f;
            if (status.Key == "TempAtk") attackMod += status.Value;
            else if (status.Key == "CantMove") hasMoveLock = 1.0f;
            else if (status.Key == "AttackLock") hasAttackLock = 1.0f;
        }
        return (attackMod, hasMoveLock, hasAttackLock, timedStatusCount);
    }

    private static string RoleFromCard(Card card) => card.Data.UnitType.ToString();

    private static int RoleRank(string role) => Array.IndexOf(RoleOrder, role) switch
    {
        -1 => 99,
        var idx => idx,
    };

    private static float[] RoleOneHot(string role) => RoleOrder.Select(name => name == role ? 1.0f : 0.0f).ToArray();

    private static float[] EffectOneHot(string effectId)
    {
        var bucket = EffectBuckets.Contains(effectId) && effectId != "Skill" ? effectId : "Skill";
        return EffectBuckets.Select(name => name == bucket ? 1.0f : 0.0f).ToArray();
    }

    private static float[] TargetOneHot(string targetType) => TargetBuckets.Select(name => name == targetType ? 1.0f : 0.0f).ToArray();

    private static float[] ResultOneHot(string result) => ResultBuckets.Select(name => name == result ? 1.0f : 0.0f).ToArray();

    private static float NormalizeRatio(float value, float scale) => scale == 0 ? 0.0f : value / scale;

    private static float NormalizePos(int value) => value < 0 ? -1.0f : value / 5.0f;

    private static float Distance(int x1, int y1, int x2, int y2)
    {
        if (x1 < 0 || y1 < 0 || x2 < 0 || y2 < 0) return -1.0f;
        return (Math.Abs(x1 - x2) + Math.Abs(y1 - y2)) / 10.0f;
    }
}
